import asyncio

from agent_fakes import FakeRoom, knowledge_over
from kb_agent.support import SupportAgent
from kb_rag import Source, index_sources
from kb_rag.testing import HASH_SETTINGS
from qdrant_client import AsyncQdrantClient

REFUNDS = Source(
    source="billing/refunds.md",
    text="# Refunds\n\nRefunds take five business days to reach your card.\n",
    markdown=True,
)
SHIPPING = Source(
    source="shipping.md",
    text="# Shipping\n\nStandard shipping arrives in three to five days.\n",
    markdown=True,
)
ANSWER = "Refunds take five business days to reach your card."


def test_the_agent_cites_the_passages_of_this_turn_that_the_answer_restates() -> None:
    async def run() -> None:
        client = AsyncQdrantClient(":memory:")
        await index_sources(client, "demo", [REFUNDS, SHIPPING], settings=HASH_SETTINGS)
        agent = SupportAgent(
            instructions="x",
            knowledge=knowledge_over(client, HASH_SETTINGS),
            room=FakeRoom(),
            api_url="http://api.test",
        )

        assert await agent.citations_for("m0", ANSWER) is None
        await agent.search_kb("refunds and shipping")  # type: ignore[operator]
        found = await agent.citations_for("m1", ANSWER)

        assert found is not None
        assert found.message_id == "m1"
        assert found.text == ANSWER
        assert [(p.title, p.source, p.anchor) for p in found.passages] == [
            ("Refunds", "billing/refunds.md", "refunds")
        ]
        assert found.passages[0].snippet.startswith("Refunds take five")
        assert await agent.citations_for("m2", "Sure, one moment.") is None
        agent.new_user_turn()
        assert await agent.citations_for("m3", ANSWER) is None

    asyncio.run(run())
