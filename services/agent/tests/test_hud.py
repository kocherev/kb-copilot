import asyncio
import json

from kb_agent.hud import HUD_TOPIC, point_payload, publish_hud, thinking_payload


class _Room:
    def __init__(self, connected: bool) -> None:
        self.connected = connected
        self.sent: list[tuple[str, bytes, bool]] = []
        self.local_participant = self

    def isconnected(self) -> bool:
        return self.connected

    async def publish_data(
        self,
        payload: bytes,
        *,
        reliable: bool = True,
        topic: str = "",
    ) -> None:
        self.sent.append((topic, payload, reliable))


def test_point_payload_clamps_and_names_the_target() -> None:
    assert point_payload(1.4, -0.2, "  Review status  ") == {
        "kind": "point",
        "x": 1.0,
        "y": 0.0,
        "label": "Review status",
    }
    assert point_payload(0.25, 0.5, "   ")["label"] == "Here"
    assert thinking_payload(True) == {"kind": "thinking", "active": True}


def test_publish_hud_sends_the_preview_topic() -> None:
    room = _Room(connected=True)

    asyncio.run(publish_hud(room, point_payload(0.2, 0.4, "Review status")))

    assert len(room.sent) == 1
    topic, payload, reliable = room.sent[0]
    assert topic == HUD_TOPIC == "hud"
    assert reliable is True
    assert json.loads(payload) == {
        "kind": "point",
        "label": "Review status",
        "x": 0.2,
        "y": 0.4,
    }
    quiet = _Room(connected=False)
    asyncio.run(publish_hud(quiet, thinking_payload(False)))
    assert quiet.sent == []
