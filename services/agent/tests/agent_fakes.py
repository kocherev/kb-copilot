import json
from collections.abc import Callable

import httpx
from kb_agent.knowledge import Knowledge
from kb_agent.local_api import local_api
from kb_rag import RetrievalSettings
from qdrant_client import AsyncQdrantClient


class FakeRoom:
    def __init__(self, connected: bool = True) -> None:
        self.name = "kb-test-room"
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


def knowledge_over(
    client: AsyncQdrantClient, settings: RetrievalSettings, product: str = "demo"
) -> Knowledge:
    http = httpx.AsyncClient(
        transport=local_api(client, settings), base_url="http://api.test"
    )
    return Knowledge(product, http)
