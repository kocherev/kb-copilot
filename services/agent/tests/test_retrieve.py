import asyncio
import json
from pathlib import Path

import pytest
from kb_agent.retrieve import NOT_IN_DOCS, search_kb, tool_text
from kb_agent.support import SupportAgent
from kb_rag.pipeline import index_sources
from kb_rag.sources import Source, iter_documents, read_source
from livekit.agents import ModelSettings
from livekit.agents.llm import ChatContext, ChatMessage
from livekit.agents.llm.tool_context import ToolFlag
from qdrant_client import QdrantClient

DEMO = Path(__file__).resolve().parents[3] / "demo" / "docs"


def _run(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())


REFUND_QUESTION = "How long do refunds take?"
OUTSIDE_QUESTION = "What is the capital of France?"


def _client() -> QdrantClient:
    client = QdrantClient(":memory:")
    index_sources(
        client,
        "demo",
        [read_source(path) for path in iter_documents(DEMO)],
    )
    index_sources(
        client,
        "other",
        [
            Source(
                source_url="file:///docs/zephyr.md",
                text="Zephyr ships on Friday.",
                markdown=False,
            )
        ],
    )
    return client


def _agent(client: QdrantClient, product_id: str = "demo") -> SupportAgent:
    return SupportAgent(
        instructions="You are the support agent for Demo.",
        product_id=product_id,
        qdrant=client,
    )


def test_search_kb_returns_the_matching_product_source() -> None:
    client = _client()

    refunds = search_kb(client, "demo", REFUND_QUESTION)
    other = search_kb(client, "other", "When does zephyr ship?")
    leaked = search_kb(client, "demo", "When does zephyr ship?")

    assert refunds.hits
    assert {hit.source_url for hit in refunds.hits} <= set(refunds.source_urls())
    assert all("billing.md" in hit.source_url for hit in refunds.hits)
    assert all(hit.text for hit in refunds.hits)
    assert "5 business days" in " ".join(hit.text for hit in refunds.hits)
    assert other.hits
    assert all("zephyr.md" in hit.source_url for hit in other.hits)
    assert not leaked.hits
    assert "not in the docs" in tool_text(leaked).lower()
    assert "zephyr.md" not in tool_text(leaked)


def test_search_kb_cites_a_source_when_a_passage_matches() -> None:
    found = search_kb(_client(), "demo", "refund")

    text = tool_text(found)
    assert found.source_urls()
    assert all(source in text for source in found.source_urls())
    assert "billing.md" in text
    assert "Say exactly" not in text


def test_search_kb_says_not_in_the_docs_when_nothing_matches() -> None:
    client = _client()

    missing = search_kb(client, "demo", OUTSIDE_QUESTION)
    empty = search_kb(client, "unused-product", REFUND_QUESTION)

    for found in (missing, empty):
        assert found.hits == ()
        assert found.source_urls() == []
        spoken = tool_text(found)
        assert "not in the docs" in spoken.lower()
        assert NOT_IN_DOCS in spoken
        assert "billing.md" not in spoken


def test_agent_tool_is_search_kb_and_cites_or_refuses(
    capsys: pytest.CaptureFixture[str],
) -> None:
    agent = _agent(_client())

    assert [tool.id for tool in agent.tools] == ["point_at", "search_kb"]
    assert agent.search_kb.id == "search_kb"
    assert agent.search_kb.info.flags & ToolFlag.IGNORE_ON_ENTER
    assert agent.point_at.info.flags & ToolFlag.IGNORE_ON_ENTER

    cited = _run(agent.search_kb(None, REFUND_QUESTION))  # type: ignore[arg-type]
    cited_log = json.loads(capsys.readouterr().out.strip().splitlines()[-1])

    assert "billing.md" in cited
    assert agent.sources
    assert cited_log["kind"] == "retrieval"
    assert cited_log["product_id"] == "demo"
    assert cited_log["hit_count"] >= 1
    assert isinstance(cited_log["duration_ms"], int)
    assert cited_log["duration_ms"] >= 0

    refused = _run(agent.search_kb(None, OUTSIDE_QUESTION))  # type: ignore[arg-type]
    refused_log = json.loads(capsys.readouterr().out.strip().splitlines()[-1])

    assert "not in the docs" in refused.lower()
    assert NOT_IN_DOCS in refused
    assert agent.sources
    assert refused_log["hit_count"] == 0


def test_turn_cites_a_demo_answer_and_refuses_outside_the_docs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    agent = _agent(_client())

    async def cited_turn() -> str:
        context = ChatContext.empty()
        await agent.on_user_turn_completed(
            context,
            ChatMessage(role="user", content=[REFUND_QUESTION]),
        )
        assert agent.sources
        lookup = context.items[-1]
        assert isinstance(lookup, ChatMessage)
        assert "billing.md" in (lookup.text_content or "")
        spoken = "Refunds take 5 business days."

        async def chunks():
            yield spoken

        parts: list[str] = []
        async for part in agent.transcription_node(chunks(), ModelSettings()):
            parts.append(str(part))
        return "".join(parts)

    transcript = _run(cited_turn())
    record = json.loads(capsys.readouterr().out.strip().splitlines()[-1])

    assert "Refunds take 5 business days." in transcript
    assert "Source: " in transcript
    assert "billing.md" in transcript
    assert record["kind"] == "retrieval"
    assert record["hit_count"] >= 1

    async def refused_turn() -> str:
        await agent.on_user_turn_completed(
            ChatContext.empty(),
            ChatMessage(role="user", content=[OUTSIDE_QUESTION]),
        )
        parts: list[str] = []
        async for part in agent.llm_node(ChatContext.empty(), [], ModelSettings()):
            parts.append(str(part))
        return "".join(parts)

    assert _run(refused_turn()) == NOT_IN_DOCS
    assert "not in the docs" in NOT_IN_DOCS.lower()


def test_greeting_is_not_a_refusal() -> None:
    agent = _agent(_client())

    async def greet() -> None:
        await agent.on_user_turn_completed(
            ChatContext.empty(),
            ChatMessage(role="user", content=["hello"]),
        )
        async for _part in agent.llm_node(ChatContext.empty(), [], ModelSettings()):
            pass

    with pytest.raises(RuntimeError, match="not running"):
        _run(greet())
