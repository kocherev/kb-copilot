"""Tables the API owns, and the request-scoped database session."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import Request
from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map = {
        datetime: DateTime(timezone=True),
        dict[str, Any]: JSON().with_variant(JSONB(), "postgresql"),
    }


class ProductRow(Base):
    __tablename__ = "products"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    org_id: Mapped[str] = mapped_column(Text, index=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    tone: Mapped[str] = mapped_column(Text)
    refusal_rules: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class ApiKeyRow(Base):
    __tablename__ = "api_keys"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    org_id: Mapped[str] = mapped_column(Text, index=True)
    name: Mapped[str] = mapped_column(Text)
    prefix: Mapped[str] = mapped_column(String(32), unique=True)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_used_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]


class AuditRow(Base):
    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    org_id: Mapped[str] = mapped_column(Text, index=True)
    actor: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    target: Mapped[str] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(default=utcnow)
    details: Mapped[dict[str, Any]] = mapped_column(default=dict)


class LiveSessionRow(Base):
    __tablename__ = "live_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    org_id: Mapped[str] = mapped_column(Text, index=True)
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE")
    )
    room: Mapped[str] = mapped_column(Text)
    user_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class LinearConnectionRow(Base):
    """An org's Linear workspace. Tokens are AES-GCM ciphertext."""

    __tablename__ = "linear_connections"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    org_id: Mapped[str] = mapped_column(Text, unique=True)
    access_token: Mapped[bytes] = mapped_column(LargeBinary)
    refresh_token: Mapped[bytes | None] = mapped_column(LargeBinary)
    expires_at: Mapped[int | None] = mapped_column(BigInteger)
    workspace_name: Mapped[str] = mapped_column(Text)
    team_id: Mapped[str] = mapped_column(Text)
    team_key: Mapped[str] = mapped_column(Text)
    team_name: Mapped[str] = mapped_column(Text)
    connected_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class LinearStateUseRow(Base):
    """An OAuth state nonce that came back once. A second use is a replay."""

    __tablename__ = "linear_state_uses"

    nonce: Mapped[str] = mapped_column(Text, primary_key=True)
    expires_at: Mapped[int] = mapped_column(BigInteger)


class EscalationRow(Base):
    """A handoff the agent proposed. It becomes a Linear issue only on approval."""

    __tablename__ = "escalations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    org_id: Mapped[str] = mapped_column(Text, index=True)
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE")
    )
    room: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    issue_identifier: Mapped[str | None] = mapped_column(Text)
    issue_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class IngestJobRow(Base):
    """One upload request. Its documents are indexed in the background."""

    __tablename__ = "ingest_jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(Text)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class DocumentRow(Base):
    """A file in a product's index. Its bytes wait here until the job indexes it."""

    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("product_id", "source"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE")
    )
    source: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    content: Mapped[bytes | None] = mapped_column(LargeBinary)
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("ingest_jobs.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class RateLimitRow(Base):
    """One fixed-window counter per org and minute."""

    __tablename__ = "rate_limit_hits"

    org_id: Mapped[str] = mapped_column(Text, primary_key=True)
    window: Mapped[int] = mapped_column(Integer, primary_key=True)
    hits: Mapped[int] = mapped_column(Integer)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessions() as session:
        yield session


def get_sessionmaker(request: Request) -> async_sessionmaker[AsyncSession]:
    """For work that must commit apart from the request's own transaction."""
    return request.app.state.sessions
