"""Join the session room, show the agent the screen, and run approved actions."""

import argparse
import asyncio
import json
import logging
from collections.abc import Awaitable, Callable

from livekit import rtc

from kb_desktop.actions import (
    METHODS,
    Action,
    Cursor,
    Display,
    Executor,
    InvalidRequest,
    Pointer,
    Screenshot,
    handle,
    parse,
)

logger = logging.getLogger("kb_desktop")

# Application codes. LiveKit reserves 1001 to 1999 for its own errors.
INVALID_REQUEST = 4000
FORBIDDEN = 4001
FAILED = 4002

# The agent reads screenshots from byte streams on this topic.
SCREENSHOT_TOPIC = "desktop.screenshot"
# A call can arrive before the room announces that its caller joined. The
# server announces a participant once its media connection is up, which took
# 3 s on a local dev server, so an unknown caller gets this long to show up.
JOIN_WAIT_SECONDS = 5.0

Capture = Callable[[Display], bytes]
ShowCursor = Callable[[Cursor, Display], None]

ACCESSIBILITY_HELP = (
    "macOS has not allowed this app to control the computer.\n"
    "Open System Settings > Privacy & Security > Accessibility, switch on the "
    "terminal you started kb-desktop from (Terminal, iTerm, VS Code), then run "
    "kb-desktop again."
)
SCREEN_RECORDING_HELP = (
    "macOS has not allowed this app to capture the screen, so the agent "
    "cannot see what it would click.\n"
    "Open System Settings > Privacy & Security > Screen & System Audio "
    "Recording, switch on the terminal you started kb-desktop from, quit and "
    "reopen that terminal, then run kb-desktop again."
)


async def is_agent(room: rtc.Room, identity: str) -> bool:
    waited = 0.0
    while (caller := room.remote_participants.get(identity)) is None:
        if waited >= JOIN_WAIT_SECONDS:
            return False
        await asyncio.sleep(0.05)
        waited += 0.05
    return caller.kind == rtc.ParticipantKind.PARTICIPANT_KIND_AGENT


def register(
    room: rtc.Room,
    display: Callable[[], Display],
    executor: Executor,
    capture: Capture,
    show_cursor: ShowCursor,
) -> None:
    """Answer the desktop.* methods, for the agent participant only."""
    one_at_a_time = asyncio.Lock()

    async def act(method: str, call: rtc.RpcInvocationData) -> str:
        async with one_at_a_time:
            return await asyncio.to_thread(
                lambda: handle(method, call.payload, display(), executor)
            )

    async def screenshot(method: str, call: rtc.RpcInvocationData) -> str:
        request = parse(Screenshot, call.payload)
        image = await asyncio.to_thread(capture, display())
        await room.local_participant.send_bytes(
            image,
            topic=SCREENSHOT_TOPIC,
            stream_id=request.stream_id,
            mime_type="image/png",
            destination_identities=[call.caller_identity],
        )
        return json.dumps({"bytes": len(image)})

    async def cursor(method: str, call: rtc.RpcInvocationData) -> str:
        show_cursor(parse(Cursor, call.payload), display())
        return json.dumps({"ok": True})

    def guarded(
        method: str,
        body: Callable[[str, rtc.RpcInvocationData], Awaitable[str]],
    ):
        async def handler(call: rtc.RpcInvocationData) -> str:
            if not await is_agent(room, call.caller_identity):
                logger.warning("refused %s from %s", method, call.caller_identity)
                raise rtc.RpcError(FORBIDDEN, "only the agent may call this helper")
            logger.info("%s %s", method, call.payload)
            try:
                return await body(method, call)
            except InvalidRequest as exc:
                raise rtc.RpcError(INVALID_REQUEST, str(exc)) from exc
            except Exception as exc:
                logger.exception("%s failed", method)
                raise rtc.RpcError(FAILED, f"{method} failed: {exc}") from exc

        return handler

    bodies = {method: act for method in METHODS} | {
        "desktop.screenshot": screenshot,
        "desktop.cursor": cursor,
    }
    for method, body in bodies.items():
        room.local_participant.register_rpc_method(method, guarded(method, body))


async def run(
    url: str,
    token: str,
    display: Callable[[], Display],
    executor: Executor,
    capture: Capture,
    show_cursor: ShowCursor,
) -> None:
    room = rtc.Room()
    left = asyncio.Event()
    room.on("disconnected", lambda reason: left.set())
    try:
        await room.connect(url, token, options=rtc.RoomOptions(auto_subscribe=False))
        register(room, display, executor, capture, show_cursor)
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
        "--dry-run",
        action="store_true",
        help="show the screen and the cursor, log actions, perform none",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    # Imported here because the modules need macOS.
    from kb_desktop import mac, overlay

    if not args.dry_run and not mac.accessibility_trusted():
        print(ACCESSIBILITY_HELP)
        return 1
    if not mac.screen_recording_allowed():
        mac.ask_for_screen_recording()
        print(SCREEN_RECORDING_HELP)
        return 1

    def log_only(action: Action, display: Display) -> None:
        point = action.at(display) if isinstance(action, Pointer) else None
        logger.info("dry run: %s at point %s", action, point)

    async def serve() -> None:
        await run(
            args.url,
            args.token,
            mac.main_display,
            log_only if args.dry_run else mac.execute,
            mac.capture,
            overlay.start(),
        )

    try:
        asyncio.run(serve())
    except rtc.ConnectError as exc:
        print(f"Could not join the room: {exc}\nA desktop token works for ten minutes.")
        return 1
    except KeyboardInterrupt:
        pass
    return 0
