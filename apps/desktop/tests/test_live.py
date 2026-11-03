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
from uuid import uuid4

import pytest
from kb_desktop import main as helper
from kb_desktop.actions import Action, Click, Cursor, Display
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
    cursors: list[Cursor] = []
    # Bigger than one RPC reply can hold, so it has to travel as a stream.
    screen = os.urandom(200_000)

    async def scenario() -> None:
        # The grants that POST /sessions/{room}/desktop-token issues.
        helper_token = token(HELPER, "standard", can_publish=False, can_subscribe=False)
        running = asyncio.create_task(
            helper.run(
                URL,
                helper_token,
                mac.main_display,
                lambda *call: seen.append(call),
                lambda display: screen,
                lambda command, display: cursors.append(command),
            )
        )
        agent = await join("agent-1", "agent")
        user = await join("user:user-a", "standard")
        streams: dict[str, asyncio.Future[bytes]] = {}

        def on_stream(reader: rtc.ByteStreamReader, sender: str) -> None:
            async def read() -> None:
                streams[reader.info.stream_id].set_result(
                    b"".join([chunk async for chunk in reader])
                )

            asyncio.ensure_future(read())

        agent.register_byte_stream_handler(helper.SCREENSHOT_TOPIC, on_stream)
        try:
            stream_id = str(uuid4())
            streams[stream_id] = asyncio.get_running_loop().create_future()
            shot = await call(
                agent, "desktop.screenshot", json.dumps({"stream_id": stream_id})
            )
            assert json.loads(shot) == {"bytes": len(screen)}
            assert await asyncio.wait_for(streams[stream_id], 10) == screen

            cursor = {"state": "about-to-click", "x": 5, "y": 6, "name": "Shawn"}
            await call(agent, "desktop.cursor", json.dumps(cursor))
            assert cursors == [Cursor.model_validate(cursor)]

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
