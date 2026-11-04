import re
from pathlib import Path

import pytest
from agent_fakes import FakeRoom
from kb_agent import protocol
from kb_agent.computer import SCREENSHOT_TOPIC
from kb_agent.protocol import HUD_TOPIC, HudPoint, publish
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[3]
CONSTANTS = {
    "AGENT_NAME": protocol.AGENT_NAME,
    "HUD_TOPIC": protocol.HUD_TOPIC,
    "CITATIONS_TOPIC": protocol.CITATIONS_TOPIC,
    "AGENT_ERROR_TOPIC": protocol.AGENT_ERROR_TOPIC,
    "ESCALATION_TOPIC": protocol.ESCALATION_TOPIC,
    "COMPUTER_TOPIC": protocol.COMPUTER_TOPIC,
    "COMPUTER_DECISION_TOPIC": protocol.COMPUTER_DECISION_TOPIC,
    "KB_PHASE_ATTRIBUTE": protocol.KB_PHASE_ATTRIBUTE,
    "KB_PHASE_WAITING_FOR_SCREEN": protocol.KB_PHASE_WAITING_FOR_SCREEN,
    "KB_PHASE_LIVE": protocol.KB_PHASE_LIVE,
}


def test_web_protocol_names_match_the_agent() -> None:
    web = (ROOT / "apps/web/src/lib/protocol.ts").read_text()
    found = dict(re.findall(r'export const (\w+) = "([^"]+)"', web))

    assert {name: found.get(name) for name in CONSTANTS} == CONSTANTS


def test_the_helper_streams_screenshots_on_the_topic_the_agent_reads() -> None:
    helper = (ROOT / "apps/desktop/src/kb_desktop/main.py").read_text()

    assert f'SCREENSHOT_TOPIC = "{SCREENSHOT_TOPIC}"' in helper


def test_the_agent_calls_only_methods_the_helper_answers() -> None:
    def methods(*paths: str) -> set[str]:
        text = "".join((ROOT / path).read_text() for path in paths)
        return set(re.findall(r'"(desktop\.\w+)"', text))

    called = methods("services/agent/src/kb_agent/computer.py")
    answered = methods(
        "apps/desktop/src/kb_desktop/actions.py", "apps/desktop/src/kb_desktop/main.py"
    )

    assert "desktop.click" in called
    assert called <= answered


def test_api_dispatches_the_agent_by_the_same_name() -> None:
    api = (ROOT / "services/api/src/kb_api/sessions.py").read_text()

    assert f'AGENT_NAME = "{protocol.AGENT_NAME}"' in api


def test_publish_sends_json_on_the_topic_or_reports_a_gone_room() -> None:
    import asyncio

    room = FakeRoom()
    sent = asyncio.run(publish(room, HUD_TOPIC, HudPoint(x=0.2, y=0.4, label="Go")))

    assert sent
    assert room.sent == [
        (HUD_TOPIC, {"kind": "point", "x": 0.2, "y": 0.4, "label": "Go"})
    ]
    assert not asyncio.run(
        publish(FakeRoom(connected=False), HUD_TOPIC, HudPoint(x=0, y=0, label="x"))
    )


def test_a_point_outside_the_frame_is_rejected() -> None:
    with pytest.raises(ValidationError):
        HudPoint(x=1.4, y=0, label="x")
    with pytest.raises(ValidationError):
        HudPoint(x=0, y=0, label="")
