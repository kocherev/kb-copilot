import asyncio
import os

import pytest
from agent_fakes import FakeRoom
from kb_agent.citations import SUPPORT_THRESHOLD, sentences, supporting_passages
from kb_agent.support import SupportAgent
from kb_rag import DEFAULT_SETTINGS, Passage
from kb_rag.testing import HASH_SETTINGS, HashDense
from qdrant_client import AsyncQdrantClient

REFUNDS = Passage(
    id="refunds",
    product_id="demo",
    source="billing/refunds.md",
    title="Refunds",
    anchor="refunds",
    text=(
        "Refunds take five business days to reach your card. Contact billing for help."
    ),
    score=1.0,
)
SHIPPING = Passage(
    id="shipping",
    product_id="demo",
    source="shipping.md",
    title="Shipping",
    anchor="shipping",
    text=(
        "Standard shipping arrives in three to five days. Express shipping costs more."
    ),
    score=0.9,
)
# Word overlap stands in for meaning, so the cutoff here is the overlap one.
LEXICAL = 0.5


def _support(answer: str) -> list[str]:
    found = supporting_passages(answer, [REFUNDS, SHIPPING], HashDense(), LEXICAL)
    return [passage.id for passage in found]


def test_a_sentence_that_restates_a_passage_cites_it() -> None:
    assert _support("Refunds take five business days to reach your card.") == [
        "refunds"
    ]


def test_each_supporting_passage_is_cited_once_in_rank_order() -> None:
    answer = (
        "Refunds take five business days to reach your card. "
        "Standard shipping arrives in three to five days."
    )

    assert _support(answer) == ["refunds", "shipping"]


def test_an_unrelated_answer_cites_nothing() -> None:
    assert _support("The weather in Lisbon is sunny today.") == []
    assert _support("That is not in the docs.") == []
    assert _support("Sure, one moment.") == []


def test_no_passages_means_no_citations() -> None:
    assert (
        supporting_passages("Refunds take five business days.", [], HashDense()) == []
    )


def test_sentences_drop_short_filler() -> None:
    assert sentences("Sure. Refunds take five business days.\nOkay!") == [
        "Refunds take five business days."
    ]


def test_the_agent_builds_a_citations_message_for_this_turns_passages() -> None:
    async def run() -> None:
        agent = SupportAgent(
            instructions="x",
            product_id="demo",
            qdrant=AsyncQdrantClient(":memory:"),
            room=FakeRoom(),
            settings=HASH_SETTINGS,
        )
        answer = "Refunds take five business days to reach your card."
        agent.turn_passages = {REFUNDS.id: REFUNDS}

        found = await agent.citations_for("m1", answer)

        assert found is not None
        assert found.message_id == "m1"
        assert found.text == answer
        assert [(p.id, p.title, p.source, p.anchor) for p in found.passages] == [
            ("refunds", "Refunds", "billing/refunds.md", "refunds")
        ]
        assert found.passages[0].snippet.startswith("Refunds take five")
        agent.new_user_turn()
        assert await agent.citations_for("m2", answer) is None

    asyncio.run(run())


@pytest.mark.skipif(
    not os.environ.get("KB_REAL_EMBEDDINGS"),
    reason="downloads the default embedding model; set KB_REAL_EMBEDDINGS=1",
)
def test_the_default_embedder_cites_a_paraphrase_and_not_another_topic() -> None:
    restated = "Your refund reaches the card within about five business days."
    off_topic = "Express shipping is the fastest delivery option available."

    kept = supporting_passages(restated, [REFUNDS, SHIPPING], DEFAULT_SETTINGS.dense)
    skipped = supporting_passages(off_topic, [REFUNDS], DEFAULT_SETTINGS.dense)

    assert [p.id for p in kept] == ["refunds"]
    assert skipped == []
    assert SUPPORT_THRESHOLD == 0.8
