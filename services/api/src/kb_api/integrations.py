"""Connect an org to its Linear workspace with OAuth."""

import logging
from collections.abc import Callable
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kb_api import linear
from kb_api.audit import audit
from kb_api.auth import AUTH_ERRORS, ErrorBody, UserPrincipal, require_user
from kb_api.db import LinearConnectionRow, LinearStateUseRow, get_db
from kb_api.linear import LinearError, TokenGrant, get_linear_http
from kb_api.linear_secrets import (
    Config,
    InvalidState,
    LinearConfig,
    decrypt,
    encrypt,
    optional_linear_config,
    sign_state,
    verify_state,
)
from kb_api.sessions import get_clock

router = APIRouter(tags=["integrations"], responses=AUTH_ERRORS)
log = logging.getLogger(__name__)

REFRESH_MARGIN_SECONDS = 60

Http = Annotated[httpx.AsyncClient, Depends(get_linear_http)]
Clock = Annotated[Callable[[], float], Depends(get_clock)]
Db = Annotated[AsyncSession, Depends(get_db)]
User = Annotated[UserPrincipal, Depends(require_user)]

NOT_CONFIGURED: dict[int | str, dict[str, object]] = {
    503: {"model": ErrorBody, "description": "Linear is not configured"},
}


class LinearStatus(BaseModel):
    enabled: bool
    connected: bool
    workspace_name: str | None = None
    team_name: str | None = None
    team_key: str | None = None


class AuthorizeUrl(BaseModel):
    url: str


class CallbackBody(BaseModel):
    code: str
    state: str


async def load_connection(db: AsyncSession, org_id: str) -> LinearConnectionRow | None:
    return await db.scalar(
        select(LinearConnectionRow).where(LinearConnectionRow.org_id == org_id)
    )


def status_of(row: LinearConnectionRow | None, enabled: bool) -> LinearStatus:
    if row is None:
        return LinearStatus(enabled=enabled, connected=False)
    return LinearStatus(
        enabled=enabled,
        connected=True,
        workspace_name=row.workspace_name,
        team_name=row.team_name,
        team_key=row.team_key,
    )


def store_grant(
    row: LinearConnectionRow, config: LinearConfig, grant: TokenGrant, now: float
) -> None:
    row.access_token = encrypt(config.key, row.org_id, grant.access_token)
    row.refresh_token = (
        encrypt(config.key, row.org_id, grant.refresh_token)
        if grant.refresh_token
        else None
    )
    row.expires_at = int(now) + grant.expires_in if grant.expires_in else None


async def authorization_for(
    db: AsyncSession,
    http: httpx.AsyncClient,
    config: LinearConfig,
    row: LinearConnectionRow,
    now: float,
) -> str:
    """The Authorization header value. An access token that is near its end is
    traded for a new one first, and Linear rotates the refresh token with it."""
    expired = (
        row.expires_at is not None and row.expires_at - REFRESH_MARGIN_SECONDS < now
    )
    if expired:
        if row.refresh_token is None:
            raise HTTPException(409, "the Linear connection expired, reconnect it")
        try:
            grant = await linear.refresh(
                http, config, decrypt(config.key, row.org_id, row.refresh_token)
            )
        except LinearError as exc:
            log.warning("Linear refresh failed for org %s: %s", row.org_id, exc)
            raise HTTPException(
                409, "the Linear connection expired, reconnect it"
            ) from exc
        store_grant(row, config, grant, now)
        await db.commit()
    return f"Bearer {decrypt(config.key, row.org_id, row.access_token)}"


@router.get("/integrations/linear")
async def linear_status(principal: User, db: Db) -> LinearStatus:
    row = await load_connection(db, principal.org_id)
    return status_of(row, optional_linear_config() is not None)


@router.get("/integrations/linear/connect", responses=NOT_CONFIGURED)
async def connect_linear(principal: User, config: Config, clock: Clock) -> AuthorizeUrl:
    """The browser sends this request with a bearer token, so a redirect would
    not carry the user. The page opens the returned URL instead."""
    state = sign_state(config.key, principal.org_id, principal.user_id, clock())
    return AuthorizeUrl(url=linear.authorize_url(config, state))


async def consume_state(db: AsyncSession, nonce: str, expires_at: int, now: float):
    """Record the nonce, or raise if it was seen. Older nonces are dropped here."""
    try:
        await db.execute(
            delete(LinearStateUseRow).where(LinearStateUseRow.expires_at < now)
        )
        db.add(LinearStateUseRow(nonce=nonce, expires_at=expires_at))
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(400, "invalid or expired state") from exc


@router.post(
    "/integrations/linear/callback",
    responses={
        400: {"model": ErrorBody, "description": "State is invalid, expired, or used"},
        502: {"model": ErrorBody, "description": "Linear did not complete the grant"},
        **NOT_CONFIGURED,
    },
)
async def linear_callback(
    body: CallbackBody,
    principal: User,
    db: Db,
    config: Config,
    http: Http,
    clock: Clock,
) -> LinearStatus:
    now = clock()
    try:
        claims = verify_state(config.key, body.state, now)
    except InvalidState as exc:
        raise HTTPException(400, "invalid or expired state") from exc
    if (claims.org_id, claims.user_id) != (principal.org_id, principal.user_id):
        raise HTTPException(400, "invalid or expired state")
    await consume_state(db, claims.nonce, claims.expires_at, now)
    try:
        grant = await linear.exchange_code(http, config, body.code)
        found = await linear.workspace(http, f"Bearer {grant.access_token}")
    except LinearError as exc:
        log.warning("Linear connect failed for org %s: %s", principal.org_id, exc)
        raise HTTPException(502, "Linear did not complete the connection") from exc
    row = await load_connection(db, principal.org_id)
    if row is None:
        row = LinearConnectionRow(org_id=principal.org_id)
        db.add(row)
    store_grant(row, config, grant, now)
    row.workspace_name = found.name
    row.team_id, row.team_key, row.team_name = (
        found.team.id,
        found.team.key,
        found.team.name,
    )
    row.connected_by = principal.user_id
    audit(
        db,
        principal,
        "linear.connect",
        f"linear:{principal.org_id}",
        {"workspace": found.name, "team": found.team.key},
    )
    await db.commit()
    return status_of(row, True)


@router.delete("/integrations/linear", status_code=204)
async def disconnect_linear(principal: User, db: Db, http: Http) -> Response:
    row = await load_connection(db, principal.org_id)
    if row is None:
        return Response(status_code=204)
    config = optional_linear_config()
    if config is not None:
        # The grant is dead for us either way, so a failed revoke is only logged.
        stored = row.refresh_token or row.access_token
        try:
            await linear.revoke(http, decrypt(config.key, row.org_id, stored))
        except LinearError as exc:
            log.warning("Linear revoke failed for org %s: %s", row.org_id, exc)
    audit(
        db,
        principal,
        "linear.disconnect",
        f"linear:{principal.org_id}",
        {"workspace": row.workspace_name},
    )
    await db.delete(row)
    await db.commit()
    return Response(status_code=204)
