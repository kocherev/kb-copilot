import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from kb_api.main import app
from kb_rag.pipeline import KB_COLLECTION
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

ROOT = Path(__file__).resolve().parents[3]

pytestmark = pytest.mark.skipif(
    os.environ.get("KB_LIVE_STORES") != "1",
    reason="set KB_LIVE_STORES=1 to hit Postgres and Qdrant",
)


def test_live_demo_folder_reaches_qdrant_and_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.dependency_overrides.clear()
    monkeypatch.setenv(
        "DATABASE_URL",
        os.environ.get(
            "DATABASE_URL",
            "postgresql://kb:replace-me@localhost:5432/kb",
        ),
    )
    monkeypatch.setenv(
        "QDRANT_URL", os.environ.get("QDRANT_URL", "http://localhost:6333")
    )
    monkeypatch.setenv("KB_DATA_ROOT", str(ROOT))
    client = TestClient(app)

    created = client.post(
        "/products/livedemo/documents",
        json={"directory": "demo/docs"},
    )

    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "indexed"
    assert body["status_log"] == ["queued", "indexing", "indexed"]
    fetched = client.get(f"/ingest-jobs/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "indexed"
    assert fetched.json()["chunk_count"] == body["chunk_count"]

    qdrant = QdrantClient(url=os.environ["QDRANT_URL"])
    points, _offset = qdrant.scroll(
        collection_name=KB_COLLECTION,
        scroll_filter=Filter(
            must=[FieldCondition(key="product_id", match=MatchValue(value="livedemo"))]
        ),
        with_payload=True,
        with_vectors=True,
        limit=50,
    )
    assert len(points) == body["chunk_count"]
    assert points
    for point in points:
        assert point.payload is not None
        assert point.payload["product_id"] == "livedemo"
        assert str(point.payload["source_url"]).startswith("file:")
        assert isinstance(point.vector, dict)
        assert "dense" in point.vector
        assert "bm25" in point.vector
