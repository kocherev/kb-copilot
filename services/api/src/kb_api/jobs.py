"""A Postgres-backed queue of ingest jobs, drained by a loop in the API process."""

import asyncio
import logging
from collections.abc import Sequence
from contextlib import suppress
from typing import Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from kb_rag import (
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
POLL_SECONDS = 5

Sessions = async_sessionmaker[AsyncSession]
Upload = tuple[str, bytes]


def get_qdrant(request: Request) -> AsyncQdrantClient:
    return request.app.state.qdrant


def source_name(filename: str) -> str:
    return f"upload://{filename}"


async def queue_documents(
    db: AsyncSession, product_id: UUID, uploads: Sequence[Upload]
) -> IngestJobRow:
    """Record one job and one document per file. Re-uploading a name replaces it."""
    job = IngestJobRow(product_id=product_id, status="queued")
    db.add(job)
    await db.flush()
    for filename, data in uploads:
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
                    content=data,
                    job_id=job.id,
                )
            )
        else:
            document.status = "queued"
            document.error = None
            document.content = data
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


async def _claim(sessions: Sessions) -> tuple[UUID, UUID, list[Upload]] | None:
    """Take the oldest queued job. SKIP LOCKED keeps two claimers off the same row."""
    async with sessions() as db:
        job = await db.scalar(
            select(IngestJobRow)
            .where(IngestJobRow.status == "queued")
            .order_by(IngestJobRow.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return None
        documents = (
            await db.scalars(
                select(DocumentRow).where(
                    DocumentRow.job_id == job.id, DocumentRow.status == "queued"
                )
            )
        ).all()
        job.status = "indexing"
        for document in documents:
            document.status = "indexing"
        await db.commit()
        uploads = [
            (document.title, document.content)
            for document in documents
            if document.content is not None
        ]
        return job.id, job.product_id, uploads


async def run_next(
    sessions: Sessions, qdrant: AsyncQdrantClient, settings: RetrievalSettings
) -> bool:
    """Index the next queued job. False when the queue is empty."""
    claimed = await _claim(sessions)
    if claimed is None:
        return False
    job_id, product_id, uploads = claimed
    for upload in uploads:
        count, error = await _index_one(qdrant, settings, product_id, upload)
        # A re-upload moves the document to a newer job, which then owns the row.
        await _save(
            sessions,
            DocumentRow,
            (DocumentRow.job_id == job_id)
            & (DocumentRow.source == source_name(upload[0])),
            status="failed" if error else "indexed",
            chunk_count=count,
            error=error,
            content=None,
        )
    async with sessions() as db:
        outcomes = (
            await db.execute(
                select(DocumentRow.status, DocumentRow.chunk_count).where(
                    DocumentRow.job_id == job_id
                )
            )
        ).all()
    failed = sum(status == "failed" for status, _ in outcomes)
    await _save(
        sessions,
        IngestJobRow,
        IngestJobRow.id == job_id,
        status="failed" if failed else "indexed",
        chunk_count=sum(count for _, count in outcomes),
        error=f"{failed} of {len(outcomes)} documents failed" if failed else None,
    )
    return True


# ponytail: one loop in one API process, one job at a time. Run more than one
# API process and a restart requeues jobs another process is still indexing; add
# a lease timestamp to the claim, or a separate worker service, before that.
async def index_forever(app: FastAPI) -> None:
    while True:
        try:
            worked = await run_next(
                app.state.sessions, app.state.qdrant, app.state.retrieval
            )
        except Exception:
            log.exception("ingest worker could not read the queue")
            worked = False
        if not worked:
            with suppress(TimeoutError):
                await asyncio.wait_for(app.state.wake.wait(), POLL_SECONDS)
            app.state.wake.clear()


async def requeue_interrupted(sessions: Sessions) -> None:
    """A job left indexing belonged to a process that is gone. Its bytes are stored."""
    async with sessions() as db:
        for table in (IngestJobRow, DocumentRow):
            await db.execute(
                update(table).where(table.status == "indexing").values(status="queued")
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
