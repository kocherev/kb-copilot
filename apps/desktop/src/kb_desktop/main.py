"""Join the session room and run the agent's approved desktop actions."""

import argparse
import asyncio
import logging
from collections.abc import Callable

from livekit import rtc

from kb_desktop.actions import (
    METHODS,
    Action,
    Display,
    Executor,
    InvalidRequest,
    Pointer,
    handle,
)

logger = logging.getLogger("kb_desktop")

# Application codes. LiveKit reserves 1001 to 1999 for its own errors.
INVALID_REQUEST = 4000
FORBIDDEN = 4001
FAILED = 4002

ACCESSIBILITY_HELP = (
    "macOS has not allowed this app to control the computer.\n"
    "Open System Settings > Privacy & Security > Accessibility, switch on the "
    "terminal you started kb-desktop from (Terminal, iTerm, VS Code), then run "
    "kb-desktop again."
)


def register(
    room: rtc.Room, display: Callable[[], Display], executor: Executor
) -> None:
    """Answer the desktop.* methods, for the agent participant only."""
    one_at_a_time = asyncio.Lock()

    def handler_for(method: str):
        async def handler(call: rtc.RpcInvocationData) -> str:
            caller = room.remote_participants.get(call.caller_identity)
            if (
                caller is None
                or caller.kind != rtc.ParticipantKind.PARTICIPANT_KIND_AGENT
            ):
                logger.warning("refused %s from %s", method, call.caller_identity)
                raise rtc.RpcError(FORBIDDEN, "only the agent may call this helper")
            logger.info("%s %s", method, call.payload)
            try:
                async with one_at_a_time:
                    return await asyncio.to_thread(
                        lambda: handle(method, call.payload, display(), executor)
                    )
            except InvalidRequest as exc:
                raise rtc.RpcError(INVALID_REQUEST, str(exc)) from exc
            except Exception as exc:
                logger.exception("%s failed", method)
                raise rtc.RpcError(FAILED, f"{method} failed: {exc}") from exc

        return handler

    for method in METHODS:
        room.local_participant.register_rpc_method(method, handler_for(method))


async def run(
    url: str, token: str, display: Callable[[], Display], executor: Executor
) -> None:
    room = rtc.Room()
    left = asyncio.Event()
    room.on("disconnected", lambda reason: left.set())
    try:
        await room.connect(url, token, options=rtc.RoomOptions(auto_subscribe=False))
        register(room, display, executor)
        logger.info("joined %s as %s", room.name, room.local_participant.identity)
        await left.wait()
    finally:
        await room.disconnect()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kb-desktop", description=__doc__)
    parser.add_argument("--url", required=True, help="LiveKit ws:// or wss:// URL")
    parser.add_argument(
        "--token", required=True, help="from POST /sessions/{room}/desktop-token"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="log actions, do nothing"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    # Imported here because the module needs macOS.
    from kb_desktop import mac

    if not args.dry_run and not mac.accessibility_trusted():
        print(ACCESSIBILITY_HELP)
        return 1

    def log_only(action: Action, display: Display) -> None:
        point = action.at(display) if isinstance(action, Pointer) else None
        logger.info("dry run: %s at point %s", action, point)

    try:
        asyncio.run(
            run(
                args.url,
                args.token,
                mac.main_display,
                log_only if args.dry_run else mac.execute,
            )
        )
    except rtc.ConnectError as exc:
        print(f"Could not join the room: {exc}\nA desktop token works for ten minutes.")
        return 1
    except KeyboardInterrupt:
        pass
    return 0
