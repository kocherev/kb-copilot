import asyncio
import os
from dataclasses import dataclass

import pytest
from kb_rag import (
    DEFAULT_SETTINGS,
    RetrievalSettings,
    Source,
    index_sources,
    search,
    supported_ids,
)
from kb_rag.citations import sentences
from kb_rag.testing import HASH_SETTINGS
from qdrant_client import AsyncQdrantClient

REFUNDS = Source(
    source="refunds.md",
    text="# Refunds\n\nRefunds take five business days to reach your card. "
    "Contact billing for help.\n",
    markdown=True,
)
SHIPPING = Source(
    source="shipping.md",
    text="# Shipping\n\nStandard shipping arrives in three to five days. "
    "Express shipping costs more.\n",
    markdown=True,
)


@dataclass
class Docs:
    client: AsyncQdrantClient
    settings: RetrievalSettings
    refunds: str
    shipping: str

    def supported(
        self, answer: str, ids: list[str], product: str = "demo"
    ) -> list[str]:
        return asyncio.run(
            supported_ids(self.client, product, answer, ids, settings=self.settings)
        )


def build(settings: RetrievalSettings) -> Docs:
    async def index() -> Docs:
        client = AsyncQdrantClient(":memory:")
        await index_sources(client, "demo", [REFUNDS, SHIPPING], settings=settings)
        await index_sources(client, "other", [REFUNDS], settings=settings)
        found = await search(client, "demo", "refunds shipping", settings=settings)
        ids = {p.source: p.id for p in found.passages}
        return Docs(client, settings, ids["refunds.md"], ids["shipping.md"])

    return asyncio.run(index())


@pytest.fixture(scope="module")
def docs() -> Docs:
    return build(HASH_SETTINGS)


def test_a_sentence_that_restates_a_passage_cites_it(docs: Docs) -> None:
    answer = "Refunds take five business days to reach your card."

    assert docs.supported(answer, [docs.refunds, docs.shipping]) == [docs.refunds]


def test_each_supported_passage_is_cited_once_in_the_order_given(docs: Docs) -> None:
    answer = (
        "Refunds take five business days to reach your card. "
        "Standard shipping arrives in three to five days."
    )

    assert docs.supported(answer, [docs.shipping, docs.refunds]) == [
        docs.shipping,
        docs.refunds,
    ]


def test_an_unrelated_answer_cites_nothing(docs: Docs) -> None:
    both = [docs.refunds, docs.shipping]

    assert docs.supported("The weather in Lisbon is sunny today.", both) == []
    assert docs.supported("That is not in the docs.", both) == []
    assert docs.supported("Sure, one moment.", both) == []


def test_an_answer_that_changes_the_facts_cites_nothing(docs: Docs) -> None:
    wrong = "Refunds take ninety business days and never reach any card."

    assert docs.supported(wrong, [docs.refunds]) == []


def test_no_passages_means_no_citations(docs: Docs) -> None:
    assert docs.supported("Refunds take five business days.", []) == []


def test_a_passage_of_another_product_is_never_cited(docs: Docs) -> None:
    answer = "Refunds take five business days to reach your card."

    assert docs.supported(answer, [docs.refunds], product="other") == []


def test_sentences_drop_short_filler() -> None:
    assert sentences("Sure. Refunds take five business days.\nOkay!") == [
        "Refunds take five business days."
    ]


@pytest.mark.skipif(
    not os.environ.get("KB_REAL_EMBEDDINGS"),
    reason="downloads the default embedding model; set KB_REAL_EMBEDDINGS=1",
)
def test_the_default_embedder_cites_a_paraphrase_and_not_another_topic() -> None:
    docs = build(DEFAULT_SETTINGS)
    restated = "Your refund reaches the card within about five business days."
    off_topic = "Express shipping is the fastest delivery option available."

    assert docs.supported(restated, [docs.refunds, docs.shipping]) == [docs.refunds]
    assert docs.supported(off_topic, [docs.refunds]) == []
