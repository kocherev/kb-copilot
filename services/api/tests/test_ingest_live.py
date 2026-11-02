import asyncio
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from kb_api.auth import Principal, get_principal
from kb_api.main import app
from kb_rag import KB_COLLECTION
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

DEMO_DOCS = Path(__file__).resolve().parents[3] / "demo" / "docs"

pytestmark = pytest.mark.skipif(
    os.environ.get("KB_LIVE_STORES") != "1",
    reason="set KB_LIVE_STORES=1 to hit Postgres and Qdrant",
)


def test_live_demo_docs_reach_qdrant_and_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        os.environ.get("DATABASE_URL", "postgresql://kb:replace-me@localhost:5432/kb"),
    )
    monkeypatch.setenv(
        "QDRANT_URL", os.environ.get("QDRANT_URL", "http://localhost:6333")
    )
    app.dependency_overrides[get_principal] = lambda: Principal(
        org_id="org-live", actor="test", user_id=None
    )
    product = {
        "name": "Live",
        "description": "Live store test.",
        "tone": "calm",
        "refusal_rules": "None.",
    }
    paths = sorted(DEMO_DOCS.rglob("*.md"))

    try:
        with TestClient(app) as client:
            product_id = client.post("/products", json=product).json()["id"]
            created = client.post(
                f"/products/{product_id}/documents",
                files=[("files", (path.name, path.read_bytes())) for path in paths],
            )
            assert created.status_code == 202
            job = client.get(f"/ingest-jobs/{created.json()['id']}").json()
            documents = client.get(f"/products/{product_id}/documents").json()
            assert job["status"] == "indexed"
            assert [d["status"] for d in documents] == ["indexed"] * len(paths)
            assert sum(d["chunk_count"] for d in documents) == job["chunk_count"] > 0

            qdrant = AsyncQdrantClient(url=os.environ["QDRANT_URL"])
            points, _offset = asyncio.run(
                qdrant.scroll(
                    collection_name=KB_COLLECTION,
                    scroll_filter=Filter(
                        must=[
                            FieldCondition(
                                key="product_id", match=MatchValue(value=product_id)
                            )
                        ]
                    ),
                    with_vectors=True,
                    limit=500,
                )
            )
            assert len(points) == job["chunk_count"]
            for point in points:
                assert isinstance(point.vector, dict)
                assert set(point.vector) == {"dense", "sparse"}

            assert client.delete(f"/products/{product_id}").status_code == 204
            points, _offset = asyncio.run(
                qdrant.scroll(
                    collection_name=KB_COLLECTION,
                    scroll_filter=Filter(
                        must=[
                            FieldCondition(
                                key="product_id", match=MatchValue(value=product_id)
                            )
                        ]
                    ),
                    limit=1,
                )
            )
            assert points == []
    finally:
        app.dependency_overrides.clear()
