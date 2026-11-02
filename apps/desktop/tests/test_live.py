"""Round trip through a real LiveKit server, with the helper in dry-run mode.

Skipped unless KB_DESKTOP_LIVE=1. Start a server with `livekit-server --dev`, or
point LIVEKIT_URL, LIVEKIT_API_KEY and LIVEKIT_API_SECRET at one. Nothing here
moves the mouse: the executor only records the action.
"""

import asyncio
import contextlib
import json
import os
from typing import Literal

import pytest
from kb_desktop import main as helper
from kb_desktop.actions import Action, Click, Display
from livekit import api, rtc

pytestmark = pytest.mark.skipif(
    os.environ.get("KB_DESKTOP_LIVE") != "1", reason="set KB_DESKTOP_LIVE=1"
)

URL = os.environ.get("LIVEKIT_URL", "ws://localhost:7880")
KEY = os.environ.get("LIVEKIT_API_KEY", "devkey")
SECRET = os.environ.get("LIVEKIT_API_SECRET", "secret")
ROOM = "kb-desktop-live-test"
HELPER = "desktop:user-a"


def token(
    identity: str,
    kind: Literal["standard", "agent"],
    can_publish: bool = True,
    can_subscribe: bool = True,
) -> str:
    return (
        api.AccessToken(KEY, SECRET)
        .with_identity(identity)
        .with_kind(kind)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=ROOM,
                can_publish=can_publish,
                can_subscribe=can_subscribe,
            )
        )
        .to_jwt()
    )


async def join(identity: str, kind: Literal["standard", "agent"]) -> rtc.Room:
    room = rtc.Room()
    await room.connect(URL, token(identity, kind))
    return room


async def call(room: rtc.Room, method: str, payload: str = "") -> str:
    # The helper registers its methods just after it joins.
    for _ in range(50):
        try:
            return await room.local_participant.perform_rpc(
                destination_identity=HELPER, method=method, payload=payload
            )
        except rtc.RpcError as exc:
            if exc.code != rtc.RpcError.ErrorCode.UNSUPPORTED_METHOD:
                raise
            await asyncio.sleep(0.1)
    raise TimeoutError(method)


def test_the_agent_reaches_the_helper_and_nobody_else_does() -> None:
    mac = pytest.importorskip("kb_desktop.mac")
    seen: list[tuple[Action, Display]] = []

    async def scenario() -> None:
        # The grants that POST /sessions/{room}/desktop-token issues.
        helper_token = token(HELPER, "standard", can_publish=False, can_subscribe=False)
        running = asyncio.create_task(
            helper.run(
                URL, helper_token, mac.main_display, lambda *call: seen.append(call)
            )
        )
        agent = await join("agent-1", "agent")
        user = await join("user:user-a", "standard")
        try:
            display = json.loads(await call(agent, "desktop.info"))
            assert display == {
                "width": mac.main_display().width,
                "height": mac.main_display().height,
                "scale": mac.main_display().scale,
            }

            reply = await call(agent, "desktop.click", '{"x": 500, "y": 250}')
            assert json.loads(reply) == {"ok": True}
            [(action, shown)] = seen
            assert isinstance(action, Click)
            assert action == Click(x=500, y=250)
            point = action.at(shown)
            assert point == (display["width"] // 2, display["height"] // 4)
            print(f"click 500,250 on {display} -> point {point}")

            with pytest.raises(rtc.RpcError) as refused:
                await call(user, "desktop.click", '{"x": 1, "y": 1}')
            assert refused.value.code == helper.FORBIDDEN
            assert len(seen) == 1
        finally:
            await agent.disconnect()
            await user.disconnect()
            running.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await running

    asyncio.run(scenario())
