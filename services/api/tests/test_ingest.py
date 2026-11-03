import asyncio
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from kb_api.db import LiveSessionRow
from kb_api.jobs import get_qdrant, requeue_interrupted
from kb_rag import KB_COLLECTION
from kb_rag.sources import MAX_BYTES
from kb_rag.testing import HASH_SETTINGS
from qdrant_client import AsyncQdrantClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

PRODUCT = {
    "name": "Acme",
    "description": "Acme helps customers reset passwords.",
    "tone": "calm and brief",
    "refusal_rules": "Do not invent a refund policy.",
}
MISSING = "00000000-0000-0000-0000-000000000000"
NOTES = b"# Notes\n\nPassword reset links expire after 30 minutes.\n"


def upload(*files: tuple[str, bytes]) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("files", (name, data, "application/octet-stream")) for name, data in files]


@pytest.fixture
def qdrant(http: TestClient) -> AsyncQdrantClient:
    from kb_api.main import app

    client = AsyncQdrantClient(":memory:")
    app.dependency_overrides[get_qdrant] = lambda: client
    app.state.qdrant = client
    app.state.retrieval = HASH_SETTINGS
    return client


@pytest.fixture
def product(http: TestClient, as_user: Callable[..., dict[str, str]]) -> str:
    created = http.post("/products", json=PRODUCT, headers=as_user())
    return created.json()["id"]


def settle(http: TestClient, headers: dict[str, str], job: str) -> None:
    """Wait for the background loop to finish the job."""
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        status = http.get(f"/ingest-jobs/{job}", headers=headers).json()["status"]
        if status not in {"queued", "indexing"}:
            return
        time.sleep(0.02)
    raise AssertionError("the job did not finish")


def ingest(
    http: TestClient, headers: dict[str, str], product: str, *files: tuple[str, bytes]
) -> dict[str, Any]:
    """Upload, wait for the background loop, and return the 202 body."""
    created = http.post(
        f"/products/{product}/documents", headers=headers, files=upload(*files)
    )
    assert created.status_code == 202
    settle(http, headers, created.json()["id"])
    return created.json()


def stored(client: AsyncQdrantClient, product_id: str) -> list[dict[str, object]]:
    points, _offset = asyncio.run(
        client.scroll(KB_COLLECTION, with_payload=True, limit=100)
    )
    return [
        point.payload
        for point in points
        if point.payload and point.payload["product_id"] == product_id
    ]


def test_anonymous_requests_are_rejected(http: TestClient) -> None:
    calls = [
        http.post(f"/products/{MISSING}/documents", files=upload(("a.md", NOTES))),
        http.get(f"/products/{MISSING}/documents"),
        http.delete(f"/products/{MISSING}/documents/{MISSING}"),
        http.get(f"/ingest-jobs/{MISSING}"),
    ]

    assert [call.status_code for call in calls] == [401] * len(calls)


def test_upload_returns_a_job_and_indexes_in_the_background(
    http: TestClient, as_user, product: str, qdrant: AsyncQdrantClient
) -> None:
    headers = as_user()

    created = http.post(
        f"/products/{product}/documents",
        headers=headers,
        files=upload(("notes.md", NOTES)),
    )

    assert created.status_code == 202
    job = created.json()
    assert job["status"] == "queued"
    assert job["product_id"] == product
    settle(http, headers, job["id"])
    done = http.get(f"/ingest-jobs/{job['id']}", headers=headers).json()
    assert done["status"] == "indexed"
    assert done["error"] is None
    assert done["chunk_count"] >= 1
    documents = http.get(f"/products/{product}/documents", headers=headers).json()
    assert [(d["title"], d["source"], d["status"], d["error"]) for d in documents] == [
        ("notes.md", "upload://notes.md", "indexed", None)
    ]
    assert documents[0]["chunk_count"] == done["chunk_count"]
    assert documents[0]["job_id"] == job["id"]
    chunks = stored(qdrant, product)
    assert len(chunks) == done["chunk_count"]
    assert {chunk["source"] for chunk in chunks} == {"upload://notes.md"}


def test_another_org_gets_404_on_every_document_route(
    http: TestClient, as_user, product: str, qdrant: AsyncQdrantClient
) -> None:
    job = ingest(http, as_user(), product, ("notes.md", NOTES))
    document = http.get(f"/products/{product}/documents", headers=as_user()).json()[0]
    other = as_user(user="user-b", org="org-b")

    calls = [
        http.post(
            f"/products/{product}/documents",
            headers=other,
            files=upload(("a.md", NOTES)),
        ),
        http.get(f"/products/{product}/documents", headers=other),
        http.delete(f"/products/{product}/documents/{document['id']}", headers=other),
        http.get(f"/ingest-jobs/{job['id']}", headers=other),
    ]

    assert [call.status_code for call in calls] == [404] * len(calls)
    assert len(stored(qdrant, product)) >= 1
    teammate = as_user(user="user-c", org="org-a")
    assert http.get(f"/ingest-jobs/{job['id']}", headers=teammate).status_code == 200


def test_uploading_the_same_name_replaces_the_document(
    http: TestClient, as_user, product: str, qdrant: AsyncQdrantClient
) -> None:
    headers = as_user()
    path = f"/products/{product}/documents"
    first = ingest(http, headers, product, ("a.md", b"Old refund text."))
    second = ingest(http, headers, product, ("a.md", b"New refund text."))

    documents = http.get(path, headers=headers).json()

    assert len(documents) == 1
    assert documents[0]["job_id"] == second["id"] != first["id"]
    assert [chunk["text"] for chunk in stored(qdrant, product)] == ["New refund text."]


def test_deleting_a_document_removes_its_row_and_chunks(
    http: TestClient, as_user, product: str, qdrant: AsyncQdrantClient
) -> None:
    headers = as_user()
    path = f"/products/{product}/documents"
    ingest(http, headers, product, ("a.md", b"About refunds."), ("b.md", NOTES))
    documents = {d["title"]: d for d in http.get(path, headers=headers).json()}

    deleted = http.delete(f"{path}/{documents['a.md']['id']}", headers=headers)

    assert deleted.status_code == 204
    remaining = http.get(path, headers=headers).json()
    assert [d["title"] for d in remaining] == ["b.md"]
    assert {chunk["source"] for chunk in stored(qdrant, product)} == {"upload://b.md"}
    again = http.delete(f"{path}/{documents['a.md']['id']}", headers=headers)
    assert again.status_code == 404


def test_the_product_list_counts_documents_and_dates_the_last_session(
    http: TestClient,
    as_user,
    product: str,
    qdrant: AsyncQdrantClient,
    sync_engine: Engine,
) -> None:
    headers = as_user()
    ingest(http, headers, product, ("a.md", NOTES), ("b.md", NOTES))
    with Session(sync_engine) as db:
        for day in (2, 1):
            db.add(
                LiveSessionRow(
                    org_id="org-a",
                    product_id=UUID(product),
                    room=f"kb-{day}",
                    created_at=datetime(2026, 11, day, 10, tzinfo=UTC),
                )
            )
        db.commit()

    [listed] = http.get("/products", headers=headers).json()

    assert listed["document_count"] == 2
    assert listed["last_session_at"].startswith("2026-11-02T10:00:00")


def test_deleting_a_product_removes_its_chunks(
    http: TestClient, as_user, product: str, qdrant: AsyncQdrantClient
) -> None:
    headers = as_user()
    ingest(http, headers, product, ("a.md", NOTES))
    assert stored(qdrant, product)

    deleted = http.delete(f"/products/{product}", headers=headers)

    assert deleted.status_code == 204
    assert stored(qdrant, product) == []


def test_deleting_a_product_removes_its_documents_and_jobs(
    http: TestClient,
    as_user,
    product: str,
    qdrant: AsyncQdrantClient,
    rows,
    sync_engine,
) -> None:
    if sync_engine.dialect.name != "postgresql":
        pytest.skip("SQLite only cascades with a PRAGMA; Postgres is what ships")
    headers = as_user()
    ingest(http, headers, product, ("a.md", NOTES))

    http.delete(f"/products/{product}", headers=headers)

    assert rows("documents") == []
    assert rows("ingest_jobs") == []


def test_an_unreadable_file_fails_with_a_stable_message(
    http: TestClient, as_user, product: str, qdrant: AsyncQdrantClient
) -> None:
    headers = as_user()

    job = ingest(
        http,
        headers,
        product,
        ("broken.pdf", b"%PDF-1.1\nnot a real pdf"),
        ("ok.md", NOTES),
    )

    done = http.get(f"/ingest-jobs/{job['id']}", headers=headers).json()
    assert (done["status"], done["error"]) == ("failed", "1 of 2 documents failed")
    documents = {
        d["title"]: d
        for d in http.get(f"/products/{product}/documents", headers=headers).json()
    }
    assert documents["broken.pdf"]["status"] == "failed"
    assert documents["broken.pdf"]["error"] == "could not read this file"
    assert documents["ok.md"]["status"] == "indexed"


def test_a_search_store_failure_does_not_leak_its_message(
    http: TestClient, as_user, product: str
) -> None:
    from kb_api.main import app

    class Broken:
        async def collection_exists(self, name: str) -> bool:
            raise RuntimeError("secret connection string")

    app.state.qdrant = Broken()
    app.state.retrieval = HASH_SETTINGS
    headers = as_user()

    ingest(http, headers, product, ("a.md", NOTES))

    listed = http.get(f"/products/{product}/documents", headers=headers)
    assert listed.json()[0]["error"] == "indexing failed"
    assert "secret" not in listed.text


@pytest.mark.parametrize(
    ("files", "detail"),
    [
        ([], "files are required"),
        (upload(("notes.exe", b"hi")), "unsupported file type: .exe"),
        (
            upload(("/etc/notes.md", NOTES)),
            "file name must be a single relative name",
        ),
        (
            upload(("../notes.md", NOTES)),
            "file name must be a single relative name",
        ),
        (upload(("a.md", NOTES), ("a.md", NOTES)), "file names must be unique"),
        (
            upload(("big.txt", b"x" * (MAX_BYTES + 1))),
            f"big.txt exceeds {MAX_BYTES} bytes",
        ),
        (
            upload(*[(f"{n}.md", NOTES) for n in range(21)]),
            "Too many files. Maximum number of files is 20.",
        ),
    ],
)
def test_invalid_uploads_are_rejected(
    http: TestClient, as_user, product: str, qdrant: AsyncQdrantClient, files, detail
) -> None:
    response = http.post(
        f"/products/{product}/documents",
        headers=as_user(),
        files=files or {"other": ("x.md", NOTES)},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": detail}
    assert http.get(f"/products/{product}/documents", headers=as_user()).json() == []


def test_a_body_that_is_not_multipart_is_rejected(
    http: TestClient, as_user, product: str, qdrant: AsyncQdrantClient
) -> None:
    response = http.post(
        f"/products/{product}/documents",
        headers=as_user(),
        json={"directory": "demo/docs"},
    )

    assert response.status_code == 400


def test_an_oversized_body_is_cut_off_while_streaming(
    http: TestClient,
    as_user,
    product: str,
    qdrant: AsyncQdrantClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("kb_api.ingest.MAX_REQUEST_BYTES", 1000)

    response = http.post(
        f"/products/{product}/documents",
        headers=as_user(),
        files=upload(("a.md", b"x" * 5000)),
    )

    assert response.status_code == 413


def test_a_document_that_is_still_indexing_cannot_be_deleted(
    http: TestClient,
    as_user,
    product: str,
    qdrant: AsyncQdrantClient,
    sync_engine: Engine,
) -> None:
    headers = as_user()
    ingest(http, headers, product, ("a.md", NOTES))
    with sync_engine.begin() as connection:
        connection.execute(text("UPDATE documents SET status = 'indexing'"))
    document = http.get(f"/products/{product}/documents", headers=headers).json()[0]

    deleted = http.delete(
        f"/products/{product}/documents/{document['id']}", headers=headers
    )
    product_deleted = http.delete(f"/products/{product}", headers=headers)

    assert deleted.status_code == 409
    assert product_deleted.status_code == 409
    assert len(http.get(f"/products/{product}/documents", headers=headers).json()) == 1


def test_a_restart_requeues_a_job_that_was_indexing_and_it_finishes(
    http: TestClient,
    as_user,
    product: str,
    qdrant: AsyncQdrantClient,
    sync_engine: Engine,
    rows,
) -> None:
    from kb_api.main import app

    headers = as_user()
    job = ingest(http, headers, product, ("a.md", NOTES))
    assert rows("documents")[0]["content"] is None
    asyncio.run(qdrant.delete_collection(KB_COLLECTION))
    with sync_engine.begin() as connection:
        connection.execute(text("UPDATE ingest_jobs SET status = 'indexing'"))
        connection.execute(
            text("UPDATE documents SET status = 'indexing', content = :bytes"),
            {"bytes": NOTES},
        )

    http.portal.call(requeue_interrupted, app.state.sessions)  # pyright: ignore[reportOptionalMemberAccess]
    http.portal.call(app.state.wake.set)  # pyright: ignore[reportOptionalMemberAccess]
    settle(http, headers, job["id"])

    done = http.get(f"/ingest-jobs/{job['id']}", headers=headers).json()
    assert (done["status"], done["error"]) == ("indexed", None)
    assert done["chunk_count"] >= 1
    assert len(stored(qdrant, product)) == done["chunk_count"]
    assert rows("documents")[0]["content"] is None


def test_openapi_describes_the_multipart_upload(http: TestClient) -> None:
    post = http.get("/openapi.json").json()["paths"][
        "/products/{product_id}/documents"
    ]["post"]

    assert "202" in post["responses"]
    assert "multipart/form-data" in post["requestBody"]["content"]


def test_a_failed_document_can_be_deleted_before_anything_was_indexed(
    http: TestClient, as_user, product: str, qdrant: AsyncQdrantClient
) -> None:
    headers = as_user()
    path = f"/products/{product}/documents"
    ingest(http, headers, product, ("broken.pdf", b"%PDF-1.1\nnope"))
    document = http.get(path, headers=headers).json()[0]

    deleted = http.delete(f"{path}/{document['id']}", headers=headers)

    assert deleted.status_code == 204
    assert http.get(path, headers=headers).json() == []
