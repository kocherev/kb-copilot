from typing import Literal, Protocol
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Json
from pydantic import BaseModel

JobStatus = Literal["queued", "indexing", "indexed", "failed"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ingest_jobs (
    id UUID PRIMARY KEY,
    product_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('queued', 'indexing', 'indexed', 'failed')
    ),
    status_log JSONB NOT NULL,
    chunk_count INTEGER NOT NULL,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


class IngestJob(BaseModel):
    id: UUID
    product_id: str
    status: JobStatus
    status_log: list[JobStatus]
    chunk_count: int = 0
    error: str | None = None


class JobStore(Protocol):
    def ensure_schema(self) -> None: ...

    def create(self, job: IngestJob) -> None: ...

    def save(self, job: IngestJob) -> None: ...

    def get(self, job_id: UUID) -> IngestJob | None: ...


class MemoryJobStore:
    def __init__(self) -> None:
        self.jobs: dict[UUID, IngestJob] = {}

    def ensure_schema(self) -> None:
        return

    def create(self, job: IngestJob) -> None:
        self.jobs[job.id] = job.model_copy(deep=True)

    def save(self, job: IngestJob) -> None:
        if job.id not in self.jobs:
            raise KeyError(job.id)
        self.jobs[job.id] = job.model_copy(deep=True)

    def get(self, job_id: UUID) -> IngestJob | None:
        job = self.jobs.get(job_id)
        if job is None:
            return None
        return job.model_copy(deep=True)


class PostgresJobStore:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._ready = False

    def _connect(self) -> Connection:
        return Connection.connect(self._database_url)

    def ensure_schema(self) -> None:
        if self._ready:
            return
        with self._connect() as connection:
            connection.execute(_SCHEMA)
        self._ready = True

    def create(self, job: IngestJob) -> None:
        self.ensure_schema()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ingest_jobs (
                    id, product_id, status, status_log, chunk_count, error
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    job.id,
                    job.product_id,
                    job.status,
                    Json(job.status_log),
                    job.chunk_count,
                    job.error,
                ),
            )

    def save(self, job: IngestJob) -> None:
        self.ensure_schema()
        with self._connect() as connection:
            updated = connection.execute(
                """
                UPDATE ingest_jobs
                SET status = %s,
                    status_log = %s,
                    chunk_count = %s,
                    error = %s,
                    updated_at = now()
                WHERE id = %s
                """,
                (
                    job.status,
                    Json(job.status_log),
                    job.chunk_count,
                    job.error,
                    job.id,
                ),
            )
            if updated.rowcount != 1:
                raise KeyError(job.id)

    def get(self, job_id: UUID) -> IngestJob | None:
        self.ensure_schema()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, product_id, status, status_log, chunk_count, error
                FROM ingest_jobs
                WHERE id = %s
                """,
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        job_id, product_id, status, status_log, chunk_count, error = row
        if not isinstance(status_log, list):
            raise TypeError("status_log must be a JSON array")
        return IngestJob.model_validate(
            {
                "id": job_id,
                "product_id": product_id,
                "status": status,
                "status_log": status_log,
                "chunk_count": chunk_count,
                "error": error,
            }
        )
