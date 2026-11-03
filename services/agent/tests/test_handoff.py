import asyncio
import json
from collections.abc import Awaitable, Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
from agent_fakes import FakeRoom
from kb_agent.handoff import transcript_excerpt
from kb_agent.protocol import ESCALATION_TOPIC
from kb_agent.support import SupportAgent
from livekit.agents.llm import ChatContext
from qdrant_client import AsyncQdrantClient

ESCALATION = {"id": "esc-1", "title": "Cannot reset", "body": "Cannot reset\n\nmore"}


class Api:
    def __init__(self) -> None:
        self.posts: list[tuple[str, dict[str, str], dict[str, object]]] = []
        self.status = 201
        self.url = ""


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> Iterator[Api]:
    state = Api()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            size = int(self.headers["content-length"])
            state.posts.append(
                (
                    self.path,
                    {"token": self.headers.get("x-internal-token", "")},
                    json.loads(self.rfile.read(size)),
                )
            )
            body = json.dumps(ESCALATION if state.status == 201 else {}).encode()
            self.send_response(state.status)
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, message: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    state.url = f"http://127.0.0.1:{server.server_address[1]}"
    monkeypatch.setenv("INTERNAL_API_TOKEN", "internal-secret")
    yield state
    server.shutdown()


async def _call(tool: Callable[..., Awaitable[str]], *args: object) -> str:
    return await tool(*args)


def _agent(room: FakeRoom, api_url: str) -> SupportAgent:
    return SupportAgent(
        instructions="You are the support agent for Demo.",
        product_id="demo",
        qdrant=AsyncQdrantClient(":memory:"),
        room=room,
        api_url=api_url,
    )


async def _with_history(agent: SupportAgent) -> None:
    chat = ChatContext()
    chat.add_message(role="user", content="my reset email never arrives")
    chat.add_message(role="assistant", content="Check spam,  then retry.")
    await agent.update_chat_ctx(chat)


def test_the_tool_posts_the_room_and_recent_talk_then_shows_the_card(
    api: Api, room: FakeRoom
) -> None:
    async def run() -> None:
        agent = _agent(room, api.url)
        await _with_history(agent)

        said = await _call(agent.handoff_to_human, "Cannot reset", "Docs are silent")

        assert "approve it there" in said
        assert api.posts == [
            (
                "/internal/escalations",
                {"token": "internal-secret"},
                {
                    "room": "kb-test-room",
                    "summary": "Cannot reset",
                    "reason": "Docs are silent",
                    "transcript": (
                        "User: my reset email never arrives\n"
                        "Agent: Check spam, then retry."
                    ),
                },
            )
        ]
        assert room.sent == [(ESCALATION_TOPIC, ESCALATION)]

    asyncio.run(run())


@pytest.mark.parametrize("status", [409, 404, 503])
def test_without_a_connection_the_model_hears_it_is_unavailable(
    api: Api, room: FakeRoom, status: int
) -> None:
    api.status = status

    async def run() -> None:
        said = await _call(_agent(room, api.url).handoff_to_human, "s", "r")

        assert "not available" in said
        assert room.sent == []

    asyncio.run(run())


def test_an_unreachable_api_is_unavailable_too(room: FakeRoom) -> None:
    async def run() -> None:
        said = await _call(
            _agent(room, "http://127.0.0.1:9").handoff_to_human, "s", "r"
        )

        assert "not available" in said
        assert room.sent == []

    asyncio.run(run())


def test_nothing_is_proposed_to_a_room_nobody_sees(api: Api) -> None:
    async def run() -> None:
        said = await _call(
            _agent(FakeRoom(connected=False), api.url).handoff_to_human, "s", "r"
        )

        assert "nothing was proposed" in said

    asyncio.run(run())


def test_the_excerpt_keeps_the_last_spoken_lines_only() -> None:
    chat = ChatContext()
    for number in range(12):
        chat.add_message(role="user", content=f"question {number}")
    chat.add_message(role="system", content="hidden rules")
    chat.add_message(role="assistant", content="x" * 1000)

    lines = transcript_excerpt(chat.items).splitlines()

    assert len(lines) == 8
    assert lines[0] == "User: question 5"
    assert lines[-1] == f"Agent: {'x' * 400}"
    assert "hidden rules" not in "\n".join(lines)
