"""Each turn of a session, sent to the API so a person can replay it.

Sending never blocks or breaks the voice loop. A turn the API does not take is
logged and dropped.
"""

import asyncio
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

import httpx
from livekit.agents.llm import ChatMessage

from kb_agent.knowledge import Knowledge, SearchResult
from kb_agent.latency import log_json, turn_stages

SEND_TIMEOUT_SECONDS = 2.0
FLUSH_TIMEOUT_SECONDS = 3.0


def iso(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, UTC).isoformat()


class TurnLog:
    """One session's turns. Keep one per session and flush it at the end."""

    def __init__(self, room: str, client: httpx.AsyncClient) -> None:
        self.room = room
        self.client = client
        # What the searches and the model reported since the last agent turn.
        self.searches: list[dict[str, object]] = []
        self.image_tokens = 0
        # The loop keeps only weak references to tasks, so hold them until done.
        self.sending: set[asyncio.Task[None]] = set()

    def searched(self, query: str, found: SearchResult, seconds: float) -> None:
        self.searches.append(
            {
                "query": query,
                "passages": [
                    {"id": p.id, "title": p.title, "source": p.source, "score": p.score}
                    for p in found.passages
                ],
                "abstained": found.abstained,
                "duration_ms": round(seconds * 1000),
            }
        )

    def on_metrics(self, record: Mapping[str, object]) -> None:
        tokens = record.get("image_tokens")
        if isinstance(tokens, int):
            self.image_tokens += tokens

    def user(self, item: ChatMessage) -> None:
        self.record(item, [], [], None)

    def assistant(self, item: ChatMessage, cited: Sequence[str]) -> None:
        searches, self.searches = self.searches, []
        tokens, self.image_tokens = self.image_tokens, 0
        self.record(item, searches, list(cited), tokens or None)

    def record(
        self,
        item: ChatMessage,
        searches: list[dict[str, object]],
        cited: list[str],
        image_tokens: int | None,
    ) -> None:
        text = item.text_content
        if not text or not text.strip():
            return
        metrics = item.metrics
        body = {
            "room": self.room,
            "role": item.role,
            "text": text,
            "started_at": iso(metrics.get("started_speaking_at", item.created_at)),
            "ended_at": iso(metrics.get("stopped_speaking_at", item.created_at)),
            "searches": searches,
            "cited": cited,
            "latency": turn_stages(item.role, metrics),
            "image_tokens": image_tokens,
        }
        task = asyncio.get_running_loop().create_task(self.send(body))
        self.sending.add(task)
        task.add_done_callback(self.sending.discard)

    async def send(self, body: Mapping[str, object]) -> None:
        try:
            reply = await self.client.post(
                "/internal/turns", json=body, timeout=SEND_TIMEOUT_SECONDS
            )
            reply.raise_for_status()
        except Exception as exc:
            log_json({"event": "turn_record_failed", "error": type(exc).__name__})

    async def flush(self) -> None:
        """Let the last turns go out, then close the client."""
        if self.sending:
            await asyncio.wait(self.sending, timeout=FLUSH_TIMEOUT_SECONDS)
        await self.client.aclose()


class LoggedKnowledge(Knowledge):
    """The knowledge base, with every search noted for the turn that uses it."""

    def __init__(
        self, product_id: str, client: httpx.AsyncClient, log: TurnLog
    ) -> None:
        super().__init__(product_id, client)
        self.log = log

    async def search(self, query: str, limit: int = 5) -> SearchResult:
        started = time.monotonic()
        found = await super().search(query, limit)
        self.log.searched(query, found, time.monotonic() - started)
        return found
