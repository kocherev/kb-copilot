"""Who is calling: a signed-in user, an org API key, or the agent service."""

import asyncio
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from kb_api.db import ApiKeyRow, get_db, utcnow
from kb_api.settings import PLACEHOLDERS, load_settings

AUDIENCE = "kb-api"
API_KEY_PREFIX = "kb_"
JWT_ALGORITHMS = ["EdDSA", "ES256", "RS256"]
# Callers choose the kid, so an unknown kid may refetch the key set only this often.
JWKS_REFETCH_COOLDOWN_SECONDS = 30.0
JWKS_TIMEOUT_SECONDS = 3.0
LAST_USED_RESOLUTION = timedelta(seconds=60)

bearer = HTTPBearer(auto_error=False)
internal_header = APIKeyHeader(
    name="X-Internal-Token", scheme_name="InternalToken", auto_error=False
)


class ErrorBody(BaseModel):
    detail: str


AUTH_ERRORS: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorBody, "description": "Missing or invalid credentials"},
    403: {"model": ErrorBody, "description": "No organization for this caller"},
}


@dataclass(frozen=True)
class Principal:
    org_id: str
    actor: str
    user_id: str | None


@dataclass(frozen=True)
class UserPrincipal(Principal):
    user_id: str


@dataclass(frozen=True)
class InternalCaller:
    """The agent service. It reads products across orgs and nothing else."""


def unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"}
    )


def jwks_client(url: str, timeout: float = JWKS_TIMEOUT_SECONDS) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(
        url,
        lifespan=300,
        timeout=timeout,
        cooldown_duration=JWKS_REFETCH_COOLDOWN_SECONDS,
    )


def hash_key(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_api_key() -> tuple[str, str]:
    """Return (prefix, token). The token is shown once and stored only as a hash."""
    prefix = secrets.token_hex(6)
    return prefix, f"{API_KEY_PREFIX}{prefix}_{secrets.token_urlsafe(32)}"


async def principal_from_api_key(db: AsyncSession, token: str) -> Principal:
    _, prefix, secret = (token.split("_", 2) + ["", ""])[:3]
    if not prefix or not secret:
        raise unauthorized("invalid API key")
    key = await db.scalar(
        select(ApiKeyRow).where(
            ApiKeyRow.prefix == prefix, ApiKeyRow.revoked_at.is_(None)
        )
    )
    if key is None or not hmac.compare_digest(key.sha256, hash_key(token)):
        raise unauthorized("invalid API key")
    now = utcnow()
    await db.execute(
        update(ApiKeyRow)
        .where(
            ApiKeyRow.id == key.id,
            or_(
                ApiKeyRow.last_used_at.is_(None),
                ApiKeyRow.last_used_at < now - LAST_USED_RESOLUTION,
            ),
        )
        .values(last_used_at=now)
        .execution_options(synchronize_session=False)
    )
    await db.commit()
    return Principal(org_id=key.org_id, actor=f"api_key:{key.id}", user_id=None)


async def principal_from_jwt(jwks: jwt.PyJWKClient, token: str) -> Principal:
    try:
        signing_key = await asyncio.to_thread(jwks.get_signing_key_from_jwt, token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=JWT_ALGORITHMS,
            audience=AUDIENCE,
            issuer=load_settings().auth_issuer,
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
    except jwt.PyJWKClientConnectionError as exc:
        raise HTTPException(status_code=503, detail="auth keys unavailable") from exc
    except jwt.PyJWTError as exc:
        raise unauthorized("invalid token") from exc
    user_id = claims["sub"]
    org_id = claims.get("org_id")
    if not isinstance(org_id, str) or not org_id:
        raise HTTPException(status_code=403, detail="no active organization")
    return Principal(org_id=org_id, actor=f"user:{user_id}", user_id=user_id)


async def get_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Principal:
    if credentials is None:
        raise unauthorized("not authenticated")
    token = credentials.credentials
    if token.startswith(API_KEY_PREFIX):
        return await principal_from_api_key(db, token)
    return await principal_from_jwt(request.app.state.jwks, token)


async def require_user(
    principal: Annotated[Principal, Depends(get_principal)],
) -> UserPrincipal:
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="sign in as a user")
    return UserPrincipal(
        org_id=principal.org_id, actor=principal.actor, user_id=principal.user_id
    )


async def get_reader(
    request: Request,
    internal_token: Annotated[str | None, Depends(internal_header)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Principal | InternalCaller:
    if internal_token is None:
        return await get_principal(request, credentials, db)
    expected = load_settings().internal_api_token.strip()
    if expected in PLACEHOLDERS:
        raise HTTPException(status_code=503, detail="internal token is not configured")
    if not hmac.compare_digest(internal_token.encode(), expected.encode()):
        raise unauthorized("invalid internal token")
    return InternalCaller()
