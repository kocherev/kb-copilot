import re
from pathlib import Path

import pytest
from agent_fakes import FakeRoom
from kb_agent import protocol
from kb_agent.protocol import HUD_TOPIC, HudPoint, publish
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[3]
CONSTANTS = {
    "AGENT_NAME": protocol.AGENT_NAME,
    "HUD_TOPIC": protocol.HUD_TOPIC,
    "CITATIONS_TOPIC": protocol.CITATIONS_TOPIC,
    "AGENT_ERROR_TOPIC": protocol.AGENT_ERROR_TOPIC,
}


def test_web_protocol_names_match_the_agent() -> None:
    web = (ROOT / "apps/web/src/lib/protocol.ts").read_text()
    found = dict(re.findall(r'export const (\w+) = "([^"]+)"', web))

    assert {name: found.get(name) for name in CONSTANTS} == CONSTANTS


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
