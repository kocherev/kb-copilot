"""Mint a participant token and dispatch the support agent."""

import json
import logging
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Annotated, Protocol
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from livekit import api
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kb_api.audit import audit
from kb_api.auth import (
    AUTH_ERRORS,
    ErrorBody,
    Principal,
    UserPrincipal,
    get_principal,
    require_user,
)
from kb_api.db import LiveSessionRow, RateLimitRow, get_db, get_sessionmaker
from kb_api.products import NOT_FOUND, load_owned_product
from kb_api.settings import PLACEHOLDERS, Settings, load_settings

router = APIRouter(tags=["sessions"], responses=AUTH_ERRORS)
logger = logging.getLogger(__name__)

AGENT_NAME = "kb-support"
WINDOW_SECONDS = 60
DESKTOP_TOKEN_TTL = timedelta(minutes=10)


class SessionCreate(BaseModel):
    product_id: UUID


class SessionGrant(BaseModel):
    url: str
    token: str
    room: str


class DesktopGrant(BaseModel):
    url: str
    token: str


class LiveSession(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    room: str
    user_id: str | None
    created_at: datetime


class AgentDispatch(BaseModel):
    agent_name: str
    room: str
    metadata: str


class Dispatcher(Protocol):
    async def create_dispatch(self, request: AgentDispatch) -> None: ...


class LiveKitDispatcher:
    def __init__(self, url: str, api_key: str, api_secret: str) -> None:
        self._url = url
        self._api_key = api_key
        self._api_secret = api_secret

    async def create_dispatch(self, request: AgentDispatch) -> None:
        async with api.LiveKitAPI(self._url, self._api_key, self._api_secret) as client:
            await client.agent_dispatch.create_dispatch(
                api.CreateAgentDispatchRequest(
                    agent_name=request.agent_name,
                    room=request.room,
                    metadata=request.metadata,
                )
            )


def livekit_ready(settings: Settings) -> bool:
    values = (
        settings.livekit_url,
        settings.livekit_api_key,
        settings.livekit_api_secret,
    )
    return all(value.strip() not in PLACEHOLDERS for value in values)


def participant_token(settings: Settings, room: str, identity: str) -> str:
    return (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(identity)
        .with_ttl(timedelta(seconds=settings.livekit_token_ttl_seconds))
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room,
                can_publish=True,
                can_subscribe=True,
            )
        )
        .to_jwt()
    )


def desktop_token(settings: Settings, room: str, user_id: str) -> str:
    """Token for the desktop helper: RPC only, no media in or out."""
    return (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(f"desktop:{user_id}")
        .with_ttl(DESKTOP_TOKEN_TTL)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room,
                can_publish=False,
                can_publish_data=True,
                can_subscribe=False,
            )
        )
        .to_jwt()
    )


def get_dispatcher() -> Dispatcher:
    settings = load_settings()
    return LiveKitDispatcher(
        settings.livekit_api_url or settings.livekit_url,
        settings.livekit_api_key,
        settings.livekit_api_secret,
    )


def get_clock() -> Callable[[], float]:
    return time.time


Sessions = async_sessionmaker[AsyncSession]


async def take_session_slot(
    sessions: Sessions, org_id: str, limit: int, now: float
) -> int:
    """Count one session start in this org's current minute, or raise 429.

    The counter commits in its own transaction. Returns the window so a failed
    dispatch can give the slot back.
    """
    window = int(now // WINDOW_SECONDS)
    bump = (
        update(RateLimitRow)
        .where(RateLimitRow.org_id == org_id, RateLimitRow.window == window)
        .values(hits=RateLimitRow.hits + 1)
        .returning(RateLimitRow.hits)
    )
    async with sessions() as db:
        hits = (await db.execute(bump)).scalar_one_or_none()
        if hits is None:
            try:
                db.add(RateLimitRow(org_id=org_id, window=window, hits=1))
                # The first start of a minute also drops the org's older windows.
                await db.execute(
                    delete(RateLimitRow).where(
                        RateLimitRow.org_id == org_id, RateLimitRow.window < window
                    )
                )
                await db.commit()
                hits = 1
            except IntegrityError:
                # A concurrent request opened this window first.
                await db.rollback()
                hits = (await db.execute(bump)).scalar_one()
        await db.commit()
    if hits > limit:
        retry_after = max(1, int((window + 1) * WINDOW_SECONDS - now))
        raise HTTPException(
            status_code=429,
            detail="too many sessions, try again shortly",
            headers={"Retry-After": str(retry_after)},
        )
    return window


async def refund_session_slot(sessions: Sessions, org_id: str, window: int) -> None:
    async with sessions() as db:
        await db.execute(
            update(RateLimitRow)
            .where(RateLimitRow.org_id == org_id, RateLimitRow.window == window)
            .values(hits=RateLimitRow.hits - 1)
        )
        await db.commit()


@router.post(
    "/sessions",
    status_code=201,
    responses={
        **NOT_FOUND,
        429: {"model": ErrorBody, "description": "Session rate limit reached"},
        502: {"model": ErrorBody, "description": "Agent dispatch failed"},
        503: {"model": ErrorBody, "description": "LiveKit is not configured"},
    },
)
async def create_session(
    body: SessionCreate,
    principal: Annotated[Principal, Depends(get_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    sessions: Annotated[Sessions, Depends(get_sessionmaker)],
    dispatcher: Annotated[Dispatcher, Depends(get_dispatcher)],
    clock: Annotated[Callable[[], float], Depends(get_clock)],
) -> SessionGrant:
    product = await load_owned_product(db, principal.org_id, body.product_id)
    settings = load_settings()
    if not livekit_ready(settings):
        raise HTTPException(status_code=503, detail="LiveKit is not configured")
    window = await take_session_slot(
        sessions, principal.org_id, settings.session_rate_limit, clock()
    )
    room = f"kb-{uuid4()}"
    grant = SessionGrant(
        url=settings.livekit_url,
        token=participant_token(settings, room, principal.actor),
        room=room,
    )
    try:
        await dispatcher.create_dispatch(
            AgentDispatch(
                agent_name=AGENT_NAME,
                room=room,
                metadata=json.dumps({"product_id": str(product.id)}),
            )
        )
    except Exception as exc:
        logger.exception("Agent dispatch failed for room %s", room)
        await refund_session_slot(sessions, principal.org_id, window)
        raise HTTPException(
            status_code=502,
            detail="Could not dispatch the agent",
        ) from exc
    session = LiveSessionRow(
        org_id=principal.org_id,
        product_id=product.id,
        room=room,
        user_id=principal.user_id,
    )
    db.add(session)
    await db.flush()
    audit(db, principal, "session.create", f"session:{session.id}", {"room": room})
    await db.commit()
    return grant


@router.get("/sessions")
async def list_sessions(
    principal: Annotated[Principal, Depends(get_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[LiveSession]:
    rows = await db.scalars(
        select(LiveSessionRow)
        .where(LiveSessionRow.org_id == principal.org_id)
        .order_by(LiveSessionRow.created_at.desc())
        .limit(100)
    )
    return [LiveSession.model_validate(row) for row in rows]


@router.post(
    "/sessions/{room}/desktop-token",
    responses={
        404: {"model": ErrorBody, "description": "No such session for this user"},
        503: {"model": ErrorBody, "description": "LiveKit is not configured"},
    },
)
async def create_desktop_token(
    room: str,
    principal: Annotated[UserPrincipal, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DesktopGrant:
    session = await db.scalar(
        select(LiveSessionRow).where(
            LiveSessionRow.org_id == principal.org_id,
            LiveSessionRow.user_id == principal.user_id,
            LiveSessionRow.room == room,
        )
    )
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    settings = load_settings()
    if not livekit_ready(settings):
        raise HTTPException(status_code=503, detail="LiveKit is not configured")
    audit(db, principal, "session.desktop_token", f"session:{session.id}")
    await db.commit()
    return DesktopGrant(
        url=settings.livekit_url,
        token=desktop_token(settings, room, principal.user_id),
    )
