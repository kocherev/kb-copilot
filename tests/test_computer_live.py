"""One computer task end to end through a real LiveKit room and Gemini.

Skipped unless KB_COMPUTER_LIVE=1 and GOOGLE_API_KEY is set. Start a server with
`livekit-server --dev`, or point LIVEKIT_URL, LIVEKIT_API_KEY and
LIVEKIT_API_SECRET at one.

The helper runs as with --dry-run: it records each action and moves nothing.
Its screen is the committed billing fixture instead of a capture, so no macOS
permission is needed. The user is a third participant that allows the first
step and stops the rest over the data channel, as the page does.
"""

import asyncio
import contextlib
import json
import os
from pathlib import Path
from typing import Any, Literal

import httpx
import pytest
from google.genai import Client
from kb_agent.computer import (
    Approvals,
    ComputerTask,
    Desktop,
    gemini_planner,
)
from kb_agent.protocol import COMPUTER_DECISION_TOPIC, COMPUTER_TOPIC, HUD_TOPIC
from kb_desktop import main as helper
from kb_desktop.actions import Action, Click, Cursor, Display
from livekit import api, rtc

pytestmark = pytest.mark.skipif(
    os.environ.get("KB_COMPUTER_LIVE") != "1" or not os.environ.get("GOOGLE_API_KEY"),
    reason="set KB_COMPUTER_LIVE=1 and GOOGLE_API_KEY",
)

ROOT = Path(__file__).resolve().parents[1]
SCREEN = (ROOT / "services/agent/tests/fixtures/billing-screen.png").read_bytes()
# The fixture is 1280 by 720. Its Update card button is centred near 412, 380.
UPDATE_CARD = (412 * 1000 // 1280, 380 * 1000 // 720)
URL = os.environ.get("LIVEKIT_URL", "ws://localhost:7880")
KEY = os.environ.get("LIVEKIT_API_KEY", "devkey")
SECRET = os.environ.get("LIVEKIT_API_SECRET", "secret")
USER = "user:live-test"
HELPER = "desktop:live-test"


def token(
    room: str, identity: str, kind: Literal["standard", "agent"], media: bool
) -> str:
    return (
        api.AccessToken(KEY, SECRET)
        .with_identity(identity)
        .with_kind(kind)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room,
                can_publish=media,
                can_publish_data=True,
                can_subscribe=media,
            )
        )
        .to_jwt()
    )


def test_a_step_is_planned_approved_by_the_user_and_run_by_the_helper() -> None:
    done: list[Action] = []
    cursor: list[Cursor] = []
    audited: list[dict[str, Any]] = []
    seen_by_user: list[tuple[str, dict[str, Any]]] = []
    said: list[str] = []

    def record(request: httpx.Request) -> httpx.Response:
        audited.append(json.loads(request.content))
        return httpx.Response(204)

    async def scenario() -> str:
        name = f"kb-computer-live-{os.getpid()}"
        running = asyncio.create_task(
            helper.run(
                URL,
                token(name, HELPER, "standard", media=False),
                lambda: Display(width=1280, height=720, scale=1.0),
                lambda action, display: done.append(action),
                lambda display: SCREEN,
                lambda command, display: cursor.append(command),
            )
        )
        user = rtc.Room()
        agent = rtc.Room()
        await user.connect(URL, token(name, USER, "standard", media=True))
        await agent.connect(URL, token(name, "agent-live", "agent", media=True))
        answers = iter(["once"])

        @user.on("data_received")
        def on_data(packet: rtc.DataPacket) -> None:
            body = json.loads(packet.data)
            seen_by_user.append((packet.topic or "", body))
            if packet.topic == COMPUTER_TOPIC and body.get("needs_approval"):
                decision = json.dumps(
                    {"id": body["id"], "decision": next(answers, "stop")}
                )
                asyncio.ensure_future(
                    user.local_participant.publish_data(
                        decision.encode(), reliable=True, topic=COMPUTER_DECISION_TOPIC
                    )
                )

        async def say(message: str) -> None:
            said.append(message)

        try:
            task = ComputerTask(
                room=agent,
                desktop=Desktop(agent, HELPER),
                approvals=Approvals(USER),
                plan=gemini_planner(Client()),
                api=httpx.AsyncClient(
                    transport=httpx.MockTransport(record), base_url="http://api.test"
                ),
                say=say,
                agent_name="Shawn",
            )
            return await task.run("Open the form to update the payment card.", ())
        finally:
            await asyncio.sleep(0.5)
            await agent.disconnect()
            await user.disconnect()
            running.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await running

    outcome = asyncio.run(scenario())

    print(f"outcome: {outcome}")
    print(f"helper performed: {done}")
    print(f"cursor states: {[c.state for c in cursor]}")
    print(f"audit: {[event['event'] for event in audited]}")
    print(f"narration: {said}")
    print(f"user saw: {seen_by_user}")
    clicks = [action for action in done if isinstance(action, Click)]
    assert clicks, "the helper received no click"
    first = clicks[0]
    assert abs(first.x - UPDATE_CARD[0]) <= 40 and abs(first.y - UPDATE_CARD[1]) <= 40
    assert len(done) == 1, "only the step the user allowed may run"
    states = [c.state for c in cursor]
    assert "about-to-click" in states and "clicking" in states
    assert states[-1] == "hidden"
    events = [event["event"] for event in audited]
    assert events[:3] == ["proposed", "approved", "performed"]
    assert events[-1] == "ended"
    topics = [topic for topic, _ in seen_by_user]
    assert COMPUTER_TOPIC in topics and HUD_TOPIC in topics
