import asyncio
from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from kb_api.settings import load_settings
from kb_rag import Source, index_sources, search
from kb_rag.testing import HASH_SETTINGS
from qdrant_client import AsyncQdrantClient

TOKEN = {"x-internal-token": "agent-secret"}
REFUNDS = Source(
    source="refunds.md",
    text="# Refunds\n\nRefunds take five business days to reach your card.\n",
    markdown=True,
)
SHIPPING = Source(
    source="shipping.md",
    text="# Shipping\n\nStandard shipping arrives in three to five days.\n",
    markdown=True,
)
ANSWER = "Refunds take five business days to reach your card."


@pytest.fixture
def index(
    http: TestClient, monkeypatch: pytest.MonkeyPatch
) -> Iterator[AsyncQdrantClient]:
    from kb_api.main import app

    monkeypatch.setenv("INTERNAL_API_TOKEN", "agent-secret")
    load_settings.cache_clear()
    client = AsyncQdrantClient(":memory:")
    asyncio.run(index_sources(client, "acme", [REFUNDS], settings=HASH_SETTINGS))
    asyncio.run(index_sources(client, "other", [SHIPPING], settings=HASH_SETTINGS))
    app.state.qdrant = client
    app.state.retrieval = HASH_SETTINGS
    yield client


def passages_of(client: AsyncQdrantClient, product: str, query: str) -> list[str]:
    found = asyncio.run(search(client, product, query, settings=HASH_SETTINGS))
    return [passage.id for passage in found.passages]


def test_search_needs_the_internal_token(http: TestClient, index: object) -> None:
    body = {"product_id": "acme", "query": "refunds"}

    assert http.post("/internal/search", json=body).status_code == 401
    assert (
        http.post(
            "/internal/search", json=body, headers={"x-internal-token": "nope"}
        ).status_code
        == 401
    )


def test_search_returns_the_products_passages_with_timings(
    http: TestClient, index: object
) -> None:
    body = {"product_id": "acme", "query": "How long do refunds take?"}

    found = http.post("/internal/search", json=body, headers=TOKEN)

    assert found.status_code == 200
    result = found.json()
    assert result["abstained"] is False
    [passage] = result["passages"]
    assert passage["source"] == "refunds.md"
    assert passage["title"] == "Refunds"
    assert passage["anchor"] == "refunds"
    assert "five business days" in passage["text"]
    assert result["timings_ms"]["total"] >= 0


def test_search_abstains_on_an_unrelated_question_and_for_another_product(
    http: TestClient, index: object
) -> None:
    unrelated = http.post(
        "/internal/search",
        json={"product_id": "acme", "query": "Zebras gallop northward"},
        headers=TOKEN,
    )
    other = http.post(
        "/internal/search",
        json={"product_id": "other", "query": "How long do refunds take?"},
        headers=TOKEN,
    )

    assert unrelated.json()["abstained"] is True
    assert unrelated.json()["passages"] == []
    assert all(p["source"] == "shipping.md" for p in other.json()["passages"])


def test_search_rejects_a_bad_product_id_or_limit(
    http: TestClient, index: object
) -> None:
    for body in (
        {"product_id": "a/b", "query": "x"},
        {"product_id": " ", "query": "x"},
        {"product_id": "acme", "query": "x", "limit": 0},
    ):
        assert (
            http.post("/internal/search", json=body, headers=TOKEN).status_code == 422
        )


def test_citations_name_the_passage_an_answer_restates(
    http: TestClient, index: AsyncQdrantClient
) -> None:
    ids = passages_of(index, "acme", "refunds five business days")
    body = {"product_id": "acme", "passage_ids": ids}

    restated = http.post(
        "/internal/citations", json={**body, "answer": ANSWER}, headers=TOKEN
    )
    unrelated = http.post(
        "/internal/citations",
        json={**body, "answer": "The weather in Lisbon is sunny today."},
        headers=TOKEN,
    )

    assert restated.json() == {"passage_ids": ids}
    assert unrelated.json() == {"passage_ids": []}


def test_citations_ignore_passages_of_another_product_and_reject_bad_ids(
    http: TestClient, index: AsyncQdrantClient
) -> None:
    ids = passages_of(index, "acme", "refunds five business days")

    foreign = http.post(
        "/internal/citations",
        json={"product_id": "other", "passage_ids": ids, "answer": ANSWER},
        headers=TOKEN,
    )
    malformed = http.post(
        "/internal/citations",
        json={"product_id": "acme", "passage_ids": ["x"], "answer": ANSWER},
        headers=TOKEN,
    )
    missing = http.post(
        "/internal/citations",
        json={"product_id": "acme", "passage_ids": [str(uuid4())], "answer": ANSWER},
        headers=TOKEN,
    )

    assert foreign.json() == {"passage_ids": []}
    assert malformed.status_code == 422
    assert missing.json() == {"passage_ids": []}


def test_the_agent_routes_are_not_in_the_public_schema(http: TestClient) -> None:
    paths = http.get("/openapi.json").json()["paths"]

    assert "/internal/search" not in paths
    assert "/internal/citations" not in paths
