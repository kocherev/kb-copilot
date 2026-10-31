from kb_rag.pipeline import KB_COLLECTION, index_sources, search_chunks
from kb_rag.sources import Source
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue


def _client() -> QdrantClient:
    return QdrantClient(":memory:")


def test_upsert_stores_product_and_source_with_hybrid_vectors() -> None:
    client = _client()
    source = Source(
        source_url="file:///docs/billing.md",
        text="# Billing\n\nRefunds take 5 business days after approval.\n",
        markdown=True,
    )

    count = index_sources(client, " acme ", [source])

    assert count >= 1
    info = client.get_collection(KB_COLLECTION)
    points, _offset = client.scroll(
        collection_name=KB_COLLECTION,
        scroll_filter=Filter(
            must=[FieldCondition(key="product_id", match=MatchValue(value="acme"))]
        ),
        with_payload=True,
        with_vectors=True,
        limit=20,
    )
    assert len(points) == count
    params = info.config.params.model_dump()
    assert "dense" in params["vectors"]
    assert "bm25" in params["sparse_vectors"]
    for point in points:
        assert point.payload is not None
        assert point.payload["product_id"] == "acme"
        assert point.payload["source_url"] == "file:///docs/billing.md"
        assert isinstance(point.vector, dict)
        assert "dense" in point.vector
        assert "bm25" in point.vector


def test_search_filters_to_the_requested_product() -> None:
    client = _client()
    index_sources(
        client,
        "acme",
        [
            Source(
                source_url="file:///docs/billing.md",
                text="Refunds take 5 business days after approval.",
                markdown=False,
            )
        ],
    )
    index_sources(
        client,
        "other",
        [
            Source(
                source_url="file:///docs/shipping.md",
                text="Shipping leaves the warehouse on Tuesday.",
                markdown=False,
            )
        ],
    )

    hits = search_chunks(client, "acme", "refunds", limit=3)
    other = search_chunks(client, "other", "refunds", limit=3)

    assert hits
    assert {hit["product_id"] for hit in hits} == {"acme"}
    assert all("billing.md" in hit["source_url"] for hit in hits)
    assert other
    assert {hit["product_id"] for hit in other} == {"other"}
    assert all("shipping.md" in hit["source_url"] for hit in other)
