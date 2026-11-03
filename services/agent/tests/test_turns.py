import asyncio
import json
from collections.abc import Callable
from types import SimpleNamespace

import httpx
import pytest
from kb_agent import session as live
from kb_agent import worker
from kb_agent.protocol import Citations, CitedPassage
from kb_agent.turns import LoggedKnowledge, TurnLog
from livekit.agents.llm import ChatMessage
from livekit.agents.metrics import RealtimeModelMetrics

ANSWER = "Refunds take five business days."


class Api:
    """The turns route of the API. `fail` is how it breaks, if it does."""

    def __init__(self, fail: Callable[[], httpx.Response] | None = None) -> None:
        self.bodies: list[dict[str, object]] = []
        self.fail = fail

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/internal/search":
            passage = {
                "id": "p1",
                "title": "Refunds",
                "source": "billing/refunds.md",
                "anchor": "refunds",
                "text": ANSWER,
                "score": 0.93,
            }
            body = {"passages": [passage], "abstained": False, "timings_ms": {}}
            return httpx.Response(200, json=body)
        if self.fail is not None:
            return self.fail()
        self.bodies.append(json.loads(request.content))
        return httpx.Response(204)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.MockTransport(self.handle), base_url="http://api.test"
        )


def message(role: str, text: str, **metrics: float) -> ChatMessage:
    return ChatMessage(
        role=role,  # type: ignore[arg-type]
        content=[text],
        created_at=1_700_000_000.0,
        metrics=metrics,  # type: ignore[arg-type]
    )


def test_a_user_and_an_assistant_turn_are_sent_with_what_the_agent_did() -> None:
    async def run() -> Api:
        api = Api()
        log = TurnLog("kb-room", api.client())
        knowledge = LoggedKnowledge("demo", api.client(), log)
        log.user(
            message(
                "user",
                "How long do refunds take?",
                started_speaking_at=1_700_000_000.0,
                stopped_speaking_at=1_700_000_002.0,
                end_of_turn_delay=0.3,
            )
        )
        await knowledge.search("refund time")
        log.on_metrics({"segment": "realtime", "image_tokens": 258})
        log.assistant(
            message("assistant", ANSWER, llm_node_ttft=0.42, e2e_latency=1.1), ["p1"]
        )
        await log.flush()
        return api

    user, assistant = asyncio.run(run()).bodies

    assert user["room"] == "kb-room"
    assert (user["role"], user["text"]) == ("user", "How long do refunds take?")
    assert user["started_at"] == "2023-11-14T22:13:20+00:00"
    assert user["ended_at"] == "2023-11-14T22:13:22+00:00"
    assert user["latency"] == {"end_of_turn_delay_ms": 300}
    assert user["searches"] == []
    assert assistant["cited"] == ["p1"]
    assert assistant["latency"] == {"llm_ttft_ms": 420, "e2e_latency_ms": 1100}
    assert assistant["image_tokens"] == 258
    [search] = assistant["searches"]  # type: ignore[misc]
    assert search["query"] == "refund time"
    assert search["abstained"] is False
    assert search["passages"] == [
        {"id": "p1", "title": "Refunds", "source": "billing/refunds.md", "score": 0.93}
    ]
    assert search["duration_ms"] >= 0


def test_a_search_belongs_to_one_agent_turn_only() -> None:
    async def run() -> Api:
        api = Api()
        log = TurnLog("kb-room", api.client())
        knowledge = LoggedKnowledge("demo", api.client(), log)
        await knowledge.search("refund time")
        log.assistant(message("assistant", ANSWER), [])
        log.assistant(message("assistant", "Anything else?"), [])
        await log.flush()
        return api

    first, second = asyncio.run(run()).bodies

    assert len(first["searches"]) == 1  # type: ignore[arg-type]
    assert second["searches"] == []
    assert second["image_tokens"] is None


def test_silence_is_not_a_turn() -> None:
    async def run() -> Api:
        api = Api()
        log = TurnLog("kb-room", api.client())
        log.user(message("user", "  "))
        await log.flush()
        return api

    assert asyncio.run(run()).bodies == []


@pytest.mark.parametrize(
    "fail",
    [
        lambda: httpx.Response(500),
        lambda: httpx.Response(401),
        lambda: (_ for _ in ()).throw(httpx.ConnectError("api is down")),
        lambda: (_ for _ in ()).throw(httpx.ReadTimeout("too slow")),
    ],
)
def test_an_api_that_fails_never_breaks_the_session(
    fail: Callable[[], httpx.Response], capsys: pytest.CaptureFixture[str]
) -> None:
    async def run() -> None:
        log = TurnLog("kb-room", Api(fail).client())
        log.user(message("user", "hello"))
        log.assistant(message("assistant", "Hi"), [])
        await log.flush()

    asyncio.run(run())

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [line["event"] for line in lines] == ["turn_record_failed"] * 2


class FakeSession:
    def __init__(self) -> None:
        self.handlers: dict[str, Callable[[object], None]] = {}

    def on(self, event: str, callback: Callable[[object], None] | None = None):
        def register(handler: Callable[[object], None]) -> Callable[[object], None]:
            self.handlers[event] = handler
            return handler

        return register(callback) if callback else register


class FakeAgent:
    def __init__(self, citations: Citations | None, fail: bool = False) -> None:
        self.citations = citations
        self.fail = fail

    def new_user_turn(self) -> None:
        return None

    async def citations_for(self, message_id: str, text: str) -> Citations | None:
        if self.fail:
            raise RuntimeError("citation check is down")
        return self.citations


def drive(agent: FakeAgent) -> list[dict[str, object]]:
    async def run() -> Api:
        api = Api()
        log = TurnLog("kb-room", api.client())
        session = FakeSession()
        worker.publish_citations(session, agent, FakeRoomNobody(), log)  # type: ignore[arg-type]
        for item in (message("user", "Refund?"), message("assistant", ANSWER)):
            session.handlers["conversation_item_added"](SimpleNamespace(item=item))
        await asyncio.gather(*worker._running)
        await log.flush()
        return api

    return asyncio.run(run()).bodies


class FakeRoomNobody:
    """A room nobody is listening in, so a citations message goes nowhere."""

    name = "kb-room"
    local_participant = SimpleNamespace()

    def isconnected(self) -> bool:
        return False


def test_the_worker_records_both_turns_with_the_cited_passage_ids() -> None:
    cited = CitedPassage(
        id="p1", title="Refunds", source="r.md", anchor="a", snippet="s"
    )
    found = Citations(message_id="m", text=ANSWER, passages=[cited])

    user, assistant = drive(FakeAgent(found))

    assert (user["role"], assistant["role"]) == ("user", "assistant")
    assert assistant["cited"] == ["p1"]


def test_a_failed_citation_check_still_records_the_turn() -> None:
    _, assistant = drive(FakeAgent(None, fail=True))

    assert assistant["text"] == ANSWER
    assert assistant["cited"] == []


def test_realtime_image_tokens_count_towards_the_next_agent_turn() -> None:
    async def run() -> int:
        log = TurnLog("kb-room", Api().client())
        session = FakeSession()
        live.attach_logs(session, log)  # type: ignore[arg-type]
        session.handlers["metrics_collected"](
            SimpleNamespace(
                metrics=RealtimeModelMetrics(
                    label="realtime",
                    request_id="rt-1",
                    timestamp=1.0,
                    duration=0.4,
                    ttft=0.2,
                    input_tokens=100,
                    output_tokens=20,
                    total_tokens=120,
                    input_token_details=RealtimeModelMetrics.InputTokenDetails(
                        image_tokens=30, audio_tokens=70
                    ),
                    output_token_details=RealtimeModelMetrics.OutputTokenDetails(
                        audio_tokens=20
                    ),
                )
            )
        )
        await log.flush()
        return log.image_tokens

    assert asyncio.run(run()) == 30


def test_tracing_is_off_without_an_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    assert worker.enable_tracing("kb-room", "demo") is None


def test_tracing_hands_livekit_a_provider_that_withholds_the_conversation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318")
    given: list[tuple[object, dict[str, object]]] = []
    monkeypatch.setattr(
        "livekit.agents.telemetry.set_tracer_provider",
        lambda provider, **options: given.append((provider, options)),
    )

    flush = worker.enable_tracing("kb-room", "demo")

    assert flush is not None
    [(provider, options)] = given
    assert type(provider).__name__ == "TracerProvider"
    assert options == {
        "metadata": {"kb.room": "kb-room", "kb.product_id": "demo"},
        "allow_pii": False,
    }
    asyncio.run(flush())
