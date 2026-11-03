"""Index uploaded documents in the background and keep their status."""

import asyncio
import logging
from collections.abc import Sequence
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, Request
from kb_rag import (
    DEFAULT_SETTINGS,
    KB_COLLECTION,
    RetrievalSettings,
    delete_source,
    index_sources,
)
from kb_rag.sources import source_from_bytes
from qdrant_client import AsyncQdrantClient
from sqlalchemy import ColumnElement, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kb_api.db import DocumentRow, IngestJobRow

log = logging.getLogger(__name__)

JobStatus = Literal["queued", "indexing", "indexed", "failed"]
PENDING = ("queued", "indexing")
# Stored errors are these fixed messages. The cause goes to the log.
UNREADABLE = "could not read this file"
INDEX_FAILED = "indexing failed"
INTERRUPTED = "interrupted by restart"

Sessions = async_sessionmaker[AsyncSession]
Upload = tuple[str, bytes]


def get_qdrant(request: Request) -> AsyncQdrantClient:
    return request.app.state.qdrant


def get_retrieval_settings() -> RetrievalSettings:
    return DEFAULT_SETTINGS


def source_name(filename: str) -> str:
    return f"upload://{filename}"


async def queue_documents(
    db: AsyncSession, product_id: UUID, uploads: Sequence[Upload]
) -> IngestJobRow:
    """Record one job and one document per file. Re-uploading a name replaces it."""
    job = IngestJobRow(product_id=product_id, status="queued")
    db.add(job)
    await db.flush()
    for filename, _ in uploads:
        document = await db.scalar(
            select(DocumentRow).where(
                DocumentRow.product_id == product_id,
                DocumentRow.source == source_name(filename),
            )
        )
        if document is None:
            db.add(
                DocumentRow(
                    product_id=product_id,
                    source=source_name(filename),
                    title=filename,
                    status="queued",
                    job_id=job.id,
                )
            )
        else:
            document.status = "queued"
            document.error = None
            document.job_id = job.id
    await db.commit()
    return job


async def _save(
    sessions: Sessions,
    table: type[IngestJobRow] | type[DocumentRow],
    where: ColumnElement[bool],
    **values: object,
) -> None:
    async with sessions() as db:
        await db.execute(update(table).where(where).values(**values))
        await db.commit()


async def _index_one(
    qdrant: AsyncQdrantClient,
    settings: RetrievalSettings,
    product_id: UUID,
    upload: Upload,
) -> tuple[int, str | None]:
    """Return the chunk count, or the stored error message."""
    filename, data = upload
    try:
        source = await asyncio.to_thread(source_from_bytes, filename, data)
    except Exception:
        log.exception("could not read %s", filename)
        return 0, UNREADABLE
    try:
        count = await index_sources(
            qdrant, str(product_id), [source], settings=settings
        )
    except Exception:
        log.exception("could not index %s", filename)
        return 0, INDEX_FAILED
    return count, None


# ponytail: jobs run in this process, so a restart interrupts them (see
# fail_interrupted). Move to a Postgres SKIP LOCKED worker if they must survive.
async def run_job(
    sessions: Sessions,
    qdrant: AsyncQdrantClient,
    settings: RetrievalSettings,
    job_id: UUID,
    product_id: UUID,
    uploads: Sequence[Upload],
) -> None:
    job = IngestJobRow.id == job_id
    await _save(sessions, IngestJobRow, job, status="indexing")
    total = failed = 0
    for upload in uploads:
        document = (DocumentRow.product_id == product_id) & (
            DocumentRow.source == source_name(upload[0])
        )
        await _save(sessions, DocumentRow, document, status="indexing")
        count, error = await _index_one(qdrant, settings, product_id, upload)
        total += count
        failed += error is not None
        await _save(
            sessions,
            DocumentRow,
            document,
            status="failed" if error else "indexed",
            chunk_count=count,
            error=error,
        )
    await _save(
        sessions,
        IngestJobRow,
        job,
        status="failed" if failed else "indexed",
        chunk_count=total,
        error=f"{failed} of {len(uploads)} documents failed" if failed else None,
    )


async def fail_interrupted(sessions: Sessions) -> None:
    """Jobs left queued or indexing belong to a process that is gone."""
    async with sessions() as db:
        for table in (IngestJobRow, DocumentRow):
            await db.execute(
                update(table)
                .where(table.status.in_(PENDING))
                .values(status="failed", error=INTERRUPTED)
            )
        await db.commit()


async def remove_chunks(
    qdrant: AsyncQdrantClient,
    product_id: UUID,
    documents: Sequence[DocumentRow],
) -> None:
    """Drop the documents' chunks from search. The caller then deletes the rows."""
    # An indexing document would write its chunks again after this delete.
    if any(document.status in PENDING for document in documents):
        raise HTTPException(409, "documents are still being indexed")
    if not documents:
        return
    try:
        # Nothing was ever indexed, so there is nothing to delete.
        if not await qdrant.collection_exists(KB_COLLECTION):
            return
        for document in documents:
            await delete_source(qdrant, str(product_id), document.source)
    except Exception as exc:
        log.exception("could not delete chunks of product %s", product_id)
        raise HTTPException(502, "could not remove indexed chunks") from exc
