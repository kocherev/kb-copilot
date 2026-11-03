import json
from collections.abc import Callable


class FakeRoom:
    def __init__(self, connected: bool = True) -> None:
        self.connected = connected
        self.sent: list[tuple[str, dict[str, object]]] = []
        self.local_participant = self
        self.remote_participants: dict[str, object] = {"user": object()}
        self.joiners: list[Callable[[object], None]] = []

    def once(self, event: str, callback: Callable[[object], None]) -> None:
        assert event == "participant_connected"
        self.joiners.append(callback)

    def isconnected(self) -> bool:
        return self.connected

    async def publish_data(
        self, payload: bytes, *, reliable: bool = True, topic: str = ""
    ) -> None:
        assert reliable
        self.sent.append((topic, json.loads(payload)))
