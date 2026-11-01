import json
from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from kb_rag.index import collection_name
from kb_rag.pipeline import index_sources
from kb_rag.sources import (
    Source,
    check_upload,
    iter_documents,
    read_source,
    source_from_bytes,
)
from qdrant_client import QdrantClient
from starlette.datastructures import UploadFile

from kb_api.jobs import IngestJob, JobStore, PostgresJobStore
from kb_api.settings import load_settings

router = APIRouter()


def get_job_store() -> JobStore:
    store = PostgresJobStore(load_settings().database_url)
    store.ensure_schema()
    return store


def get_qdrant() -> QdrantClient:
    settings = load_settings()
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
    )


def resolve_directory(data_root: str, directory: str) -> Path:
    if not directory.strip():
        raise ValueError("directory is required")
    root = Path(data_root).resolve()
    try:
        candidate = (root / directory).resolve()
    except (OSError, RuntimeError) as exc:
        raise ValueError("directory is invalid") from exc
    if not candidate.is_relative_to(root):
        raise ValueError("directory must stay inside the data root")
    if not candidate.is_dir():
        raise ValueError("directory not found")
    return candidate


def run_ingest(
    store: JobStore,
    qdrant: QdrantClient,
    product_id: str,
    load_sources: Callable[[], list[Source]],
) -> IngestJob:
    job = IngestJob(
        id=uuid4(),
        product_id=product_id,
        status="queued",
        status_log=["queued"],
    )
    store.create(job)
    job.status = "indexing"
    job.status_log.append("indexing")
    store.save(job)
    try:
        # shortcut: index inside the request. Revisit when a folder needs a worker.
        # shortcut: removed files stay indexed. Revisit when delete is an API.
        sources = load_sources()
        if not sources:
            raise ValueError("no supported documents")
        job.chunk_count = index_sources(qdrant, product_id, sources)
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        job.status_log.append("failed")
        store.save(job)
        return job
    job.status = "indexed"
    job.status_log.append("indexed")
    store.save(job)
    return job


async def loader_from_request(request: Request) -> Callable[[], list[Source]]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            payload = await request.json()
        except json.JSONDecodeError as exc:
            raise ValueError("body must be JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("body must be an object")
        directory = payload.get("directory")
        if not isinstance(directory, str):
            raise ValueError("directory is required")
        folder = resolve_directory(load_settings().data_root, directory)
        paths = iter_documents(folder)
        if not paths:
            raise ValueError("directory has no supported documents")

        def load_directory() -> list[Source]:
            return [read_source(path) for path in paths]

        return load_directory

    form = await request.form()
    uploads = form.getlist("files")
    if not uploads:
        raise ValueError("files are required")
    pending: list[tuple[str, bytes]] = []
    for upload in uploads:
        if not isinstance(upload, UploadFile):
            raise ValueError("file body must be bytes")
        filename = upload.filename
        if not isinstance(filename, str):
            raise ValueError("file name is required")
        data = await upload.read()
        check_upload(filename, data)
        pending.append((filename, data))

    def load_uploads() -> list[Source]:
        return [source_from_bytes(filename, data) for filename, data in pending]

    return load_uploads


@router.post("/products/{product_id}/documents", status_code=201)
async def create_documents(
    product_id: str,
    request: Request,
    store: JobStore = Depends(get_job_store),
    qdrant: QdrantClient = Depends(get_qdrant),
) -> IngestJob:
    try:
        collection_name(product_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        load_sources = await loader_from_request(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return run_ingest(store, qdrant, product_id.strip(), load_sources)


@router.get("/ingest-jobs/{job_id}")
def read_job(job_id: str, store: JobStore = Depends(get_job_store)) -> IngestJob:
    try:
        parsed = UUID(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="job id must be a UUID") from exc
    job = store.get(parsed)
    if job is None:
        raise HTTPException(status_code=404, detail="ingest job not found")
    return job
