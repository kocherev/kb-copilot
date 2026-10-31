from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from kb_api.ingest import get_job_store, get_qdrant
from kb_api.jobs import MemoryJobStore
from kb_api.main import app
from kb_rag.pipeline import KB_COLLECTION
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def indexed_client(monkeypatch: pytest.MonkeyPatch):
    store = MemoryJobStore()
    qdrant = QdrantClient(":memory:")
    app.dependency_overrides[get_job_store] = lambda: store
    app.dependency_overrides[get_qdrant] = lambda: qdrant
    monkeypatch.setenv("KB_DATA_ROOT", str(ROOT))
    client = TestClient(app)
    yield client, qdrant
    app.dependency_overrides.clear()


def test_demo_directory_indexes_and_records_status(indexed_client) -> None:
    client, qdrant = indexed_client

    created = client.post(
        "/products/demo/documents",
        json={"directory": "demo/docs"},
    )

    assert created.status_code == 201
    body = created.json()
    assert body["product_id"] == "demo"
    assert body["status"] == "indexed"
    assert body["status_log"] == ["queued", "indexing", "indexed"]
    assert body["chunk_count"] >= 1
    assert body["error"] is None

    fetched = client.get(f"/ingest-jobs/{body['id']}")

    assert fetched.status_code == 200
    assert fetched.json()["status"] == "indexed"
    assert fetched.json()["status_log"] == ["queued", "indexing", "indexed"]

    points, _offset = qdrant.scroll(
        collection_name=KB_COLLECTION,
        scroll_filter=Filter(
            must=[FieldCondition(key="product_id", match=MatchValue(value="demo"))]
        ),
        with_payload=True,
        with_vectors=True,
        limit=50,
    )
    assert len(points) == body["chunk_count"]
    names = set()
    for point in points:
        assert point.payload is not None
        assert point.payload["product_id"] == "demo"
        source_url = str(point.payload["source_url"])
        assert source_url.startswith("file:")
        names.add(Path(source_url).name)
        assert isinstance(point.vector, dict)
        assert "dense" in point.vector
        assert "bm25" in point.vector
    assert {"billing.md", "account.html", "README.md"} <= names


def test_upload_file_uses_upload_source_url(indexed_client) -> None:
    client, qdrant = indexed_client

    created = client.post(
        "/products/acme/documents",
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

    assert created.status_code == 201
    assert created.json()["status"] == "indexed"
    points, _offset = qdrant.scroll(
        collection_name=KB_COLLECTION,
        with_payload=True,
        limit=10,
    )
    assert points[0].payload is not None
    assert points[0].payload["source_url"] == "upload://notes.md"
    assert points[0].payload["product_id"] == "acme"


def test_directory_escape_is_rejected(indexed_client, tmp_path: Path) -> None:
    client, _qdrant = indexed_client
    outside = tmp_path / "secret.md"
    outside.write_text("hidden")

    response = client.post(
        "/products/demo/documents",
        json={"directory": "../"},
    )

    assert response.status_code == 400
    assert client.get("/ingest-jobs/not-a-uuid").status_code == 400


def test_symlink_outside_the_data_root_is_rejected(
    indexed_client, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _qdrant = indexed_client
    root = tmp_path / "data"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("Secret token stays out of the index.")
    (root / "alias").symlink_to(outside)
    monkeypatch.setenv("KB_DATA_ROOT", str(root))

    response = client.post(
        "/products/demo/documents",
        json={"directory": "alias"},
    )

    assert response.status_code == 400
    assert "data root" in response.json()["detail"]


def test_bad_pdf_marks_the_job_failed(indexed_client) -> None:
    client, _qdrant = indexed_client

    created = client.post(
        "/products/demo/documents",
        files=[
            ("files", ("broken.pdf", b"%PDF-1.1\nnot a real pdf", "application/pdf"))
        ],
    )

    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "failed"
    assert body["status_log"] == ["queued", "indexing", "failed"]
    assert body["error"]
    fetched = client.get(f"/ingest-jobs/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "failed"


def test_unsupported_upload_is_rejected(indexed_client) -> None:
    client, _qdrant = indexed_client

    response = client.post(
        "/products/acme/documents",
        files=[("files", ("notes.exe", b"hello", "application/octet-stream"))],
    )

    assert response.status_code == 400
    assert "unsupported" in response.json()["detail"]


def test_missing_job_is_not_found(indexed_client) -> None:
    client, _qdrant = indexed_client

    missing = client.get("/ingest-jobs/00000000-0000-0000-0000-000000000000")

    assert missing.status_code == 404
