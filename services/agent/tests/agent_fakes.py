import asyncio
import json
from collections.abc import AsyncIterator, Callable
from types import SimpleNamespace

import httpx
from kb_agent.knowledge import Knowledge
from kb_agent.local_api import local_api
from kb_rag import RetrievalSettings
from livekit import rtc
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


class FakeReader:
    def __init__(self, stream_id: str, data: bytes) -> None:
        self.info = SimpleNamespace(stream_id=stream_id)
        self.data = data

    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield self.data[: len(self.data) // 2]
        yield self.data[len(self.data) // 2 :]


class DesktopFakeRoom(FakeRoom):
    """A room with the user's desktop helper in it.

    The helper records every RPC and streams SCREEN back for a screenshot. The
    user answers each proposal that needs approval with the next of `answers`,
    a (sender, decision) pair, and never answers once they run out.
    """

    SCREEN = b"\x89PNG screen"

    def __init__(self, user: str = "user:abc", helper: bool = True) -> None:
        super().__init__()
        self.user = user
        self.helper = "desktop:abc"
        self.remote_participants = {user: object()}
        if helper:
            self.remote_participants[self.helper] = object()
        self.rpcs: list[tuple[str, dict[str, object]]] = []
        self.failing: dict[str, rtc.RpcError] = {}
        self.answers: list[tuple[str, str]] = []
        # 0 answers inside publish_data, before the agent can start waiting.
        self.answer_after = 0.01
        self.streams: dict[str, Callable[[object, str], None]] = {}
        self.listeners: list[Callable[[object], None]] = []

    def register_byte_stream_handler(
        self, topic: str, handler: Callable[[object, str], None]
    ) -> None:
        assert topic not in self.streams
        self.streams[topic] = handler

    def unregister_byte_stream_handler(self, topic: str) -> None:
        del self.streams[topic]

    def on(self, event: str, callback: Callable[[object], None]) -> None:
        assert event == "data_received"
        self.listeners.append(callback)

    def off(self, event: str, callback: Callable[[object], None]) -> None:
        self.listeners.remove(callback)

    async def perform_rpc(
        self,
        *,
        destination_identity: str,
        method: str,
        payload: str,
        response_timeout: float | None = None,
    ) -> str:
        assert destination_identity == self.helper
        body = json.loads(payload)
        self.rpcs.append((method, body))
        if method in self.failing:
            raise self.failing[method]
        if method == "desktop.screenshot":
            handler = self.streams["desktop.screenshot"]
            handler(FakeReader(body["stream_id"], self.SCREEN), self.helper)
            return json.dumps({"bytes": len(self.SCREEN)})
        return json.dumps({"ok": True})

    def decide(self, sender: str, proposal: str, decision: str) -> None:
        packet = SimpleNamespace(
            topic="computer-decision",
            data=json.dumps({"id": proposal, "decision": decision}).encode(),
            participant=SimpleNamespace(identity=sender),
        )
        for listener in list(self.listeners):
            listener(packet)

    async def publish_data(
        self, payload: bytes, *, reliable: bool = True, topic: str = ""
    ) -> None:
        await super().publish_data(payload, reliable=reliable, topic=topic)
        body = json.loads(payload)
        if topic == "computer" and body.get("needs_approval") and self.answers:
            sender, decision = self.answers.pop(0)
            if self.answer_after == 0:
                self.decide(sender, body["id"], decision)
                return
            asyncio.get_running_loop().call_later(
                self.answer_after, self.decide, sender, body["id"], decision
            )

    def actions(self) -> list[str]:
        """The RPCs that change something on the computer."""
        looks = ("desktop.screenshot", "desktop.cursor")
        return [method for method, _ in self.rpcs if method not in looks]
