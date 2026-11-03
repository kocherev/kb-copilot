"""Upload, list and delete a product's documents. Indexing runs in the background."""

from collections.abc import AsyncGenerator, AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
)
from kb_rag import RetrievalSettings
from kb_rag.sources import MAX_BYTES, check_upload
from pydantic import BaseModel, ConfigDict
from qdrant_client import AsyncQdrantClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from kb_api.auth import AUTH_ERRORS, ErrorBody, Principal, get_principal
from kb_api.db import DocumentRow, IngestJobRow, ProductRow, get_db, get_sessionmaker
from kb_api.jobs import (
    JobStatus,
    Sessions,
    Upload,
    get_qdrant,
    get_retrieval_settings,
    queue_documents,
    remove_chunks,
    run_job,
)
from kb_api.products import NOT_FOUND, owned_product

MAX_FILES = 20
# The form fields and part headers add a little to the files themselves.
MAX_REQUEST_BYTES = MAX_FILES * MAX_BYTES + 100_000

router = APIRouter(tags=["documents"], responses=AUTH_ERRORS)

UPLOAD_ERRORS: dict[int | str, dict[str, object]] = {
    400: {"model": ErrorBody, "description": "Missing, invalid or duplicate files"},
    404: NOT_FOUND[404],
    413: {"model": ErrorBody, "description": "The upload is too large"},
}
MULTIPART_FILES = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["files"],
                    "properties": {
                        "files": {
                            "type": "array",
                            "items": {"type": "string", "format": "binary"},
                        }
                    },
                }
            }
        },
    }
}


class IngestJob(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    status: JobStatus
    chunk_count: int
    error: str | None


class Document(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: str
    title: str
    status: JobStatus
    chunk_count: int
    error: str | None
    job_id: UUID


async def capped(stream: AsyncIterator[bytes]) -> AsyncGenerator[bytes, None]:
    """Stop reading the request body once it is larger than any valid upload."""
    total = 0
    async for chunk in stream:
        total += len(chunk)
        if total > MAX_REQUEST_BYTES:
            raise HTTPException(413, "upload is too large")
        yield chunk


async def read_uploads(request: Request) -> list[Upload]:
    if not request.headers.get("content-type", "").startswith("multipart/form-data"):
        raise HTTPException(400, "send the files as multipart/form-data")
    try:
        form = await MultiPartParser(
            request.headers,
            capped(request.stream()),
            max_files=MAX_FILES,
            max_fields=0,
        ).parse()
    except MultiPartException as exc:
        raise HTTPException(400, exc.message) from exc
    try:
        uploads: list[Upload] = []
        for upload in form.getlist("files"):
            if not isinstance(upload, UploadFile) or not upload.filename:
                raise HTTPException(400, "files must be file uploads")
            if upload.size is not None and upload.size > MAX_BYTES:
                raise HTTPException(400, f"{upload.filename} exceeds {MAX_BYTES} bytes")
            data = await upload.read()
            try:
                uploads.append((check_upload(upload.filename, data), data))
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
    finally:
        await form.close()
    names = [name for name, _ in uploads]
    if not names:
        raise HTTPException(400, "files are required")
    if len(set(names)) != len(names):
        raise HTTPException(400, "file names must be unique")
    return uploads


@router.post(
    "/products/{product_id}/documents",
    status_code=202,
    responses=UPLOAD_ERRORS,
    openapi_extra=MULTIPART_FILES,
)
async def create_documents(
    request: Request,
    product: Annotated[ProductRow, Depends(owned_product)],
    db: Annotated[AsyncSession, Depends(get_db)],
    sessions: Annotated[Sessions, Depends(get_sessionmaker)],
    qdrant: Annotated[AsyncQdrantClient, Depends(get_qdrant)],
    settings: Annotated[RetrievalSettings, Depends(get_retrieval_settings)],
    background: BackgroundTasks,
) -> IngestJob:
    uploads = await read_uploads(request)
    job = await queue_documents(db, product.id, uploads)
    background.add_task(
        run_job, sessions, qdrant, settings, job.id, product.id, uploads
    )
    return IngestJob.model_validate(job)


@router.get("/products/{product_id}/documents", responses=NOT_FOUND)
async def list_documents(
    product: Annotated[ProductRow, Depends(owned_product)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Document]:
    rows = await db.scalars(
        select(DocumentRow)
        .where(DocumentRow.product_id == product.id)
        .order_by(DocumentRow.title)
    )
    return [Document.model_validate(row) for row in rows]


@router.delete(
    "/products/{product_id}/documents/{document_id}",
    status_code=204,
    responses={
        **NOT_FOUND,
        409: {"model": ErrorBody, "description": "The document is still indexing"},
    },
)
async def delete_document(
    document_id: UUID,
    product: Annotated[ProductRow, Depends(owned_product)],
    db: Annotated[AsyncSession, Depends(get_db)],
    qdrant: Annotated[AsyncQdrantClient, Depends(get_qdrant)],
) -> Response:
    document = await db.scalar(
        select(DocumentRow).where(
            DocumentRow.id == document_id, DocumentRow.product_id == product.id
        )
    )
    if document is None:
        raise HTTPException(404, "document not found")
    await remove_chunks(qdrant, product.id, [document])
    await db.delete(document)
    await db.commit()
    return Response(status_code=204)


@router.get("/ingest-jobs/{job_id}", responses=NOT_FOUND)
async def read_job(
    job_id: UUID,
    principal: Annotated[Principal, Depends(get_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> IngestJob:
    job = await db.scalar(
        select(IngestJobRow)
        .join(ProductRow, ProductRow.id == IngestJobRow.product_id)
        .where(IngestJobRow.id == job_id, ProductRow.org_id == principal.org_id)
    )
    if job is None:
        raise HTTPException(404, "ingest job not found")
    return IngestJob.model_validate(job)
