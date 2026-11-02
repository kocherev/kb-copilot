"""Org API keys for machine clients. Only the SHA-256 of a key is stored."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kb_api.audit import audit
from kb_api.auth import (
    AUTH_ERRORS,
    ErrorBody,
    UserPrincipal,
    hash_key,
    new_api_key,
    require_user,
)
from kb_api.db import ApiKeyRow, get_db, utcnow

router = APIRouter(tags=["api-keys"], responses=AUTH_ERRORS)


class ApiKeyCreate(BaseModel):
    name: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=120, pattern=r"^[^\r\n]*$"
        ),
    ]


class ApiKey(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class ApiKeyCreated(ApiKey):
    secret: str


@router.post("/api-keys", status_code=201)
async def create_api_key(
    body: ApiKeyCreate,
    principal: Annotated[UserPrincipal, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiKeyCreated:
    prefix, token = new_api_key()
    row = ApiKeyRow(
        org_id=principal.org_id, name=body.name, prefix=prefix, sha256=hash_key(token)
    )
    db.add(row)
    await db.flush()
    audit(db, principal, "api_key.create", f"api_key:{row.id}", {"name": row.name})
    await db.commit()
    return ApiKeyCreated.model_validate(
        {**ApiKey.model_validate(row).model_dump(), "secret": token}
    )


@router.get("/api-keys")
async def list_api_keys(
    principal: Annotated[UserPrincipal, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ApiKey]:
    rows = await db.scalars(
        select(ApiKeyRow)
        .where(ApiKeyRow.org_id == principal.org_id)
        .order_by(ApiKeyRow.created_at.desc())
    )
    return [ApiKey.model_validate(row) for row in rows]


@router.delete(
    "/api-keys/{key_id}",
    status_code=204,
    responses={404: {"model": ErrorBody, "description": "No such key in this org"}},
)
async def revoke_api_key(
    key_id: UUID,
    principal: Annotated[UserPrincipal, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    row = await db.scalar(
        select(ApiKeyRow).where(
            ApiKeyRow.id == key_id, ApiKeyRow.org_id == principal.org_id
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="API key not found")
    if row.revoked_at is None:
        row.revoked_at = utcnow()
        audit(db, principal, "api_key.revoke", f"api_key:{row.id}", {"name": row.name})
        await db.commit()
    return Response(status_code=204)
