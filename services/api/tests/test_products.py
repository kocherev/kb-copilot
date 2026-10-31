from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from kb_api.ingest import get_job_store, get_qdrant
from kb_api.jobs import MemoryJobStore
from kb_api.main import app
from kb_api.products import MemoryProductStore, get_product_store
from kb_api.settings import load_settings
from kb_rag.pipeline import KB_COLLECTION
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

VALID = {
    "name": "Acme",
    "description": "Acme helps customers reset passwords.",
    "tone": "calm and brief",
    "refusal_rules": "Do not invent a refund policy.",
}


@pytest.fixture
def client():
    products = MemoryProductStore()
    qdrant = QdrantClient(":memory:")
    app.dependency_overrides[get_product_store] = lambda: products
    app.dependency_overrides[get_job_store] = lambda: MemoryJobStore()
    app.dependency_overrides[get_qdrant] = lambda: qdrant
    test_client = TestClient(app)
    yield test_client, qdrant
    app.dependency_overrides.clear()


def test_settings_read_cors_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000, http://127.0.0.1:3000")

    assert load_settings().cors_origins == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_create_get_and_put_product_config(
    client: tuple[TestClient, QdrantClient],
) -> None:
    http, _qdrant = client

    created = http.post("/products", json=VALID)

    assert created.status_code == 201
    body = created.json()
    UUID(body["id"])
    assert body["name"] == "Acme"
    assert body["description"] == VALID["description"]
    assert body["tone"] == "calm and brief"
    assert body["refusal_rules"] == "Do not invent a refund policy."

    fetched = http.get(f"/products/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == body

    updated = http.put(
        f"/products/{body['id']}",
        json={
            "name": "Acme Care",
            "description": "Acme Care answers billing questions.",
            "tone": "warm and direct",
            "refusal_rules": (
                "Do not share another customer's invoices.\nDo not promise a refund."
            ),
        },
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == body["id"]
    assert updated.json()["name"] == "Acme Care"
    assert "invoices" in updated.json()["refusal_rules"]
    assert http.get(f"/products/{body['id']}").json()["tone"] == "warm and direct"

    short = http.post("/products", json={**VALID, "name": "A"})
    assert short.status_code == 201
    assert short.json()["name"] == "A"

    padded = http.post("/products", json={**VALID, "tone": "  brief  "})
    assert padded.status_code == 201
    assert padded.json()["tone"] == "brief"


def test_invalid_product_config_is_rejected(
    client: tuple[TestClient, QdrantClient],
) -> None:
    http, _qdrant = client

    missing = http.get("/products/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404
    rejected = http.get("/products/not-a-uuid")
    assert rejected.status_code == 422
    assert rejected.json()["detail"][0]["loc"] == ["path", "product_id"]
    assert http.put("/products/not-a-uuid", json=VALID).status_code == 422

    created = http.post("/products", json=VALID)
    assert created.status_code == 201
    missing_put = http.put(
        "/products/00000000-0000-0000-0000-000000000000",
        json=VALID,
    )
    assert missing_put.status_code == 404

    empty = http.post("/products", json={**VALID, "name": "  "})
    assert empty.status_code == 400
    assert "name" in empty.json()["detail"]

    paragraph = http.post(
        "/products",
        json={**VALID, "description": "Line one.\nLine two."},
    )
    assert paragraph.status_code == 400
    assert "paragraph" in paragraph.json()["detail"]

    long_name = http.post("/products", json={**VALID, "name": "A" * 121})
    assert long_name.status_code == 400
    assert "120" in long_name.json()["detail"]

    blank_rules = http.put(
        f"/products/{created.json()['id']}",
        json={**VALID, "refusal_rules": "\n"},
    )
    assert blank_rules.status_code == 400
    assert "refusal" in blank_rules.json()["detail"]


def test_created_product_can_be_indexed(
    client: tuple[TestClient, QdrantClient],
) -> None:
    http, qdrant = client
    created = http.post("/products", json=VALID)
    assert created.status_code == 201
    product_id = created.json()["id"]

    uploaded = http.post(
        f"/products/{product_id}/documents",
        files=[
            (
                "files",
                (
                    "notes.md",
                    b"# Notes\n\nPassword reset links expire after 30 minutes.\n",
                    "text/markdown",
                ),
            )
        ],
    )

    assert uploaded.status_code == 201
    assert uploaded.json()["status"] == "indexed"
    assert uploaded.json()["product_id"] == product_id
    assert uploaded.json()["chunk_count"] >= 1

    points, _offset = qdrant.scroll(
        collection_name=KB_COLLECTION,
        scroll_filter=Filter(
            must=[FieldCondition(key="product_id", match=MatchValue(value=product_id))]
        ),
        with_payload=True,
        limit=10,
    )
    assert points
    assert points[0].payload is not None
    assert points[0].payload["product_id"] == product_id
    assert points[0].payload["source_url"] == "upload://notes.md"


def test_browser_origin_can_call_the_api(
    client: tuple[TestClient, QdrantClient],
) -> None:
    http, _qdrant = client
    allowed = http.options(
        "/products",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    local = http.options(
        "/products",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert local.status_code == 200
    assert local.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"

    blocked = http.get("/health", headers={"Origin": "http://evil.example"})
    assert blocked.headers.get("access-control-allow-origin") != "http://evil.example"
