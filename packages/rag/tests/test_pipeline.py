import asyncio
from dataclasses import replace
from pathlib import Path

import pytest
from kb_rag import (
    KB_COLLECTION,
    Source,
    delete_source,
    index_sources,
    read_directory,
    search,
    validate_product_id,
)
from kb_rag.sources import source_from_bytes
from kb_rag.testing import HASH_SETTINGS
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

REFUND_QUESTION = "How long do refunds take?"
SHIPPING_QUESTION = "When do Zephyr orders leave the warehouse?"
DEMO = Path(__file__).resolve().parents[3] / "demo" / "docs"
REFUNDS = Source(
    source="billing/refunds.md",
    text=(
        "# Refunds\n\n## Refund timing\n\n"
        "Refunds take 5 business days after the review team approves the request.\n"
    ),
    markdown=True,
)
SHIPPING = Source(
    source="shipping.md",
    text="# Shipping\n\nZephyr orders leave the warehouse on Tuesday.\n",
    markdown=True,
)


async def _points(client: AsyncQdrantClient, product_id: str):
    points, _offset = await client.scroll(
        collection_name=KB_COLLECTION,
        scroll_filter=Filter(
            must=[FieldCondition(key="product_id", match=MatchValue(value=product_id))]
        ),
        with_payload=True,
        with_vectors=True,
        limit=500,
    )
    return points


def test_index_stores_relative_sources_and_hybrid_vectors() -> None:
    async def run():
        client = AsyncQdrantClient(":memory:")
        count = await index_sources(
            client, "demo", read_directory(DEMO), settings=HASH_SETTINGS
        )
        upload = source_from_bytes("notes.md", b"# Notes\n\nReset links expire.\n")
        await index_sources(client, "demo", [upload], settings=HASH_SETTINGS)
        return count, await _points(client, "demo")

    count, points = asyncio.run(run())

    assert len(points) == count + 1
    sources = set()
    for point in points:
        assert point.payload is not None
        source = str(point.payload["source"])
        sources.add(source)
        assert not source.startswith(("/", "file:"))
        assert str(DEMO) not in str(point.payload)
        assert str(Path.home()) not in str(point.payload)
        assert isinstance(point.vector, dict)
        assert set(point.vector) == {"dense", "sparse"}
    assert {
        "billing/refunds.md",
        "accounts/password-reset.html",
        "upload://notes.md",
    } <= sources


def test_absolute_or_escaping_sources_are_rejected() -> None:
    async def run(source: str) -> None:
        bad = Source(source=source, text="Some text.", markdown=False)
        await index_sources(
            AsyncQdrantClient(":memory:"), "demo", [bad], settings=HASH_SETTINGS
        )

    for source in ("/Users/me/docs/a.md", "file:///docs/a.md", "../a.md", "C:\\a.md"):
        with pytest.raises(ValueError, match="relative path"):
            asyncio.run(run(source))


def test_reindex_replaces_a_source_without_duplicates() -> None:
    shorter = Source(
        source="billing/refunds.md", text="Refunds are reviewed.", markdown=False
    )

    async def run():
        client = AsyncQdrantClient(":memory:")
        await index_sources(client, "acme", [REFUNDS, SHIPPING], settings=HASH_SETTINGS)
        first = await _points(client, "acme")
        await index_sources(client, "acme", [REFUNDS, SHIPPING], settings=HASH_SETTINGS)
        again = await _points(client, "acme")
        await index_sources(client, "acme", [shorter], settings=HASH_SETTINGS)
        replaced = await _points(client, "acme")
        await delete_source(client, "acme", "shipping.md")
        return first, again, replaced, await _points(client, "acme")

    first, again, replaced, deleted = asyncio.run(run())

    assert sorted(str(p.id) for p in first) == sorted(str(p.id) for p in again)
    refund_texts = [
        p.payload["text"]
        for p in replaced
        if p.payload and p.payload["source"] == "billing/refunds.md"
    ]
    assert refund_texts == ["Refunds are reviewed."]
    assert {p.payload["source"] for p in deleted if p.payload} == {"billing/refunds.md"}


def test_search_stays_within_one_product_and_abstains_on_a_miss() -> None:
    async def run():
        client = AsyncQdrantClient(":memory:")
        await index_sources(client, "acme", [REFUNDS], settings=HASH_SETTINGS)
        await index_sources(client, "other", [SHIPPING], settings=HASH_SETTINGS)
        return (
            await search(client, "acme", REFUND_QUESTION, settings=HASH_SETTINGS),
            await search(client, "acme", SHIPPING_QUESTION, settings=HASH_SETTINGS),
            await search(
                client, "acme", "Zebras gallop northward", settings=HASH_SETTINGS
            ),
            await search(client, "acme", "   ", settings=HASH_SETTINGS),
        )

    refund, leaked, outside, empty = asyncio.run(run())

    assert not refund.abstained
    top = refund.passages[0]
    assert (top.product_id, top.source, top.title, top.anchor) == (
        "acme",
        "billing/refunds.md",
        "Refund timing",
        "refund-timing",
    )
    assert "5 business days" in top.text
    assert {"embed", "query", "rerank", "total"} <= set(refund.timings_ms)
    assert 0 < top.score <= 1
    for result in (leaked, outside, empty):
        assert result.abstained
        assert result.passages == ()


def test_product_id_validation() -> None:
    assert validate_product_id(" acme ") == "acme"
    with pytest.raises(ValueError, match="required"):
        validate_product_id("  ")
    with pytest.raises(ValueError, match="slashes"):
        validate_product_id("acme/docs")


class _PreferShipping:
    def scores(self, query: str, texts: list[str]) -> list[float]:
        return [5.0 if "Zephyr" in text else -5.0 for text in texts]


def test_an_opt_in_reranker_reorders_and_sets_the_score() -> None:
    both = Source(
        source="mixed.md",
        text="# Mixed\n\n## Refunds\n\nRefunds take 5 business days.\n\n"
        "## Shipping\n\nZephyr orders leave the warehouse on Tuesday.\n",
        markdown=True,
    )
    reranked = replace(HASH_SETTINGS, reranker=_PreferShipping(), abstain_threshold=0)

    async def run():
        client = AsyncQdrantClient(":memory:")
        await index_sources(client, "acme", [both], settings=reranked)
        return await search(client, "acme", REFUND_QUESTION, settings=reranked)

    found = asyncio.run(run())

    assert [p.title for p in found.passages] == ["Shipping", "Refunds"]
    assert [p.score for p in found.passages] == [5.0, -5.0]
    assert not found.abstained
