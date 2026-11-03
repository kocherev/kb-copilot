import asyncio
import json
from collections.abc import AsyncIterable
from pathlib import Path

import pytest
from kb_agent.retrieve import tool_text
from kb_agent.support import SupportAgent
from kb_rag import NOT_IN_DOCS, Source, index_sources, read_directory, search
from kb_rag.testing import HASH_SETTINGS
from livekit.agents import ModelSettings
from livekit.agents.llm import ChatContext, ChatMessage
from livekit.agents.llm.tool_context import ToolFlag
from qdrant_client import AsyncQdrantClient, QdrantClient

DEMO = Path(__file__).resolve().parents[3] / "demo" / "docs"
REFUND_QUESTION = "How long do refunds take?"
OUTSIDE_QUESTION = "Zebras gallop northward"


def _run(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())


def _client() -> AsyncQdrantClient:
    async def build() -> AsyncQdrantClient:
        client = AsyncQdrantClient(":memory:")
        await index_sources(
            client, "demo", read_directory(DEMO), settings=HASH_SETTINGS
        )
        await index_sources(
            client,
            "other",
            [
                Source(
                    source="zephyr.md", text="Zephyr ships on Friday.", markdown=False
                )
            ],
            settings=HASH_SETTINGS,
        )
        return client

    return _run(build())


def _agent(
    client: AsyncQdrantClient | QdrantClient, product_id: str = "demo"
) -> SupportAgent:
    return SupportAgent(
        instructions="You are the support agent for Demo.",
        product_id=product_id,
        qdrant=client,
        settings=HASH_SETTINGS,
    )


def test_tool_text_lists_passages_or_says_not_in_the_docs() -> None:
    client = _client()

    refunds = _run(search(client, "demo", REFUND_QUESTION, settings=HASH_SETTINGS))
    leaked = _run(
        search(client, "demo", "When does zephyr ship?", settings=HASH_SETTINGS)
    )

    assert "billing/refunds.md" in tool_text(refunds)
    assert "[1] source: billing/refunds.md" in tool_text(refunds)
    assert "Say exactly" not in tool_text(refunds)
    assert leaked.abstained
    assert NOT_IN_DOCS in tool_text(leaked)
    assert "zephyr.md" not in tool_text(leaked)


def test_agent_tool_is_search_kb_and_cites_or_refuses(
    capsys: pytest.CaptureFixture[str],
) -> None:
    agent = _agent(_client())

    assert [tool.id for tool in agent.tools] == ["point_at", "search_kb"]
    assert agent.search_kb.info.flags & ToolFlag.IGNORE_ON_ENTER
    assert agent.point_at.info.flags & ToolFlag.IGNORE_ON_ENTER

    cited = _run(agent.search_kb(None, REFUND_QUESTION))  # type: ignore[arg-type]
    cited_log = json.loads(capsys.readouterr().out.strip().splitlines()[-1])

    assert "billing/refunds.md" in cited
    assert "billing/refunds.md" in agent.sources
    assert cited_log["kind"] == "retrieval"
    assert cited_log["product_id"] == "demo"
    assert cited_log["hit_count"] >= 1
    assert cited_log["abstained"] is False
    assert isinstance(cited_log["duration_ms"], int)

    refused = _run(agent.search_kb(None, OUTSIDE_QUESTION))  # type: ignore[arg-type]
    refused_log = json.loads(capsys.readouterr().out.strip().splitlines()[-1])

    assert NOT_IN_DOCS in refused
    assert refused_log["hit_count"] == 0
    assert refused_log["abstained"] is True


def test_turn_cites_a_demo_answer_and_asks_for_the_refusal_outside_the_docs() -> None:
    agent = _agent(_client())

    async def turn(question: str) -> tuple[str, str]:
        context = ChatContext.empty()
        await agent.on_user_turn_completed(
            context, ChatMessage(role="user", content=[question])
        )
        lookup = context.items[-1]
        assert isinstance(lookup, ChatMessage)

        async def chunks():
            yield "Spoken answer."

        parts = [
            str(part)
            async for part in agent.transcription_node(chunks(), ModelSettings())
        ]
        return lookup.text_content or "", "".join(parts)

    lookup, transcript = _run(turn(REFUND_QUESTION))

    assert "source: billing/refunds.md" in lookup
    assert transcript.startswith("Spoken answer.\nSource: ")
    assert "\nSource: billing/refunds.md" in transcript

    lookup, transcript = _run(turn(OUTSIDE_QUESTION))

    assert f"say exactly: {NOT_IN_DOCS}" in lookup
    assert "Source:" not in transcript


def test_greeting_is_not_forced_into_a_refusal() -> None:
    agent = _agent(_client())

    async def greet() -> None:
        await agent.on_user_turn_completed(
            ChatContext.empty(),
            ChatMessage(role="user", content=["hello"]),
        )
        node = agent.llm_node(ChatContext.empty(), [], ModelSettings())
        assert isinstance(node, AsyncIterable)
        async for _part in node:
            pass

    # The default model node runs, and it needs a live session.
    with pytest.raises(RuntimeError, match="not running"):
        _run(greet())


def test_a_sync_client_is_turned_into_an_async_one() -> None:
    sync = QdrantClient(url="http://localhost:6333", check_compatibility=False)

    agent = _agent(sync)

    assert isinstance(agent.qdrant, AsyncQdrantClient)
