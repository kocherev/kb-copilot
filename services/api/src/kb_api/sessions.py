"""Mint a participant token and dispatch the support agent."""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Annotated, Protocol
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from livekit import api
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from kb_api.audit import audit
from kb_api.auth import AUTH_ERRORS, ErrorBody, Principal, get_principal
from kb_api.db import LiveSessionRow, RateLimitRow, get_db
from kb_api.products import NOT_FOUND, load_owned_product
from kb_api.settings import PLACEHOLDERS, Settings, load_settings

router = APIRouter(tags=["sessions"], responses=AUTH_ERRORS)
logger = logging.getLogger(__name__)

AGENT_NAME = "kb-support"
WINDOW_SECONDS = 60


class SessionCreate(BaseModel):
    product_id: UUID


class SessionGrant(BaseModel):
    url: str
    token: str
    room: str


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


def get_dispatcher() -> Dispatcher:
    settings = load_settings()
    return LiveKitDispatcher(
        settings.livekit_api_url or settings.livekit_url,
        settings.livekit_api_key,
        settings.livekit_api_secret,
    )


async def take_session_slot(db: AsyncSession, org_id: str, limit: int) -> None:
    """Count one session start in this org's current minute, or raise 429."""
    now = time.time()
    window = int(now // WINDOW_SECONDS)
    insert = (
        postgres_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    )
    statement = insert(RateLimitRow).values(org_id=org_id, window=window, hits=1)
    hits = await db.scalar(
        statement.on_conflict_do_update(
            index_elements=[RateLimitRow.org_id, RateLimitRow.window],
            set_={"hits": RateLimitRow.hits + 1},
        ).returning(RateLimitRow.hits)
    )
    await db.execute(
        delete(RateLimitRow).where(
            RateLimitRow.org_id == org_id, RateLimitRow.window < window
        )
    )
    await db.commit()
    if hits is not None and hits > limit:
        retry_after = max(1, int((window + 1) * WINDOW_SECONDS - now))
        raise HTTPException(
            status_code=429,
            detail="too many sessions, try again shortly",
            headers={"Retry-After": str(retry_after)},
        )


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
    dispatcher: Annotated[Dispatcher, Depends(get_dispatcher)],
) -> SessionGrant:
    product = await load_owned_product(db, principal.org_id, body.product_id)
    settings = load_settings()
    if not livekit_ready(settings):
        raise HTTPException(status_code=503, detail="LiveKit is not configured")
    await take_session_slot(db, principal.org_id, settings.session_rate_limit)
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
