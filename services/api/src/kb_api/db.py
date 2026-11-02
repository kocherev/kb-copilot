"""Tables the API owns, and the request-scoped database session."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import Request
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
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
