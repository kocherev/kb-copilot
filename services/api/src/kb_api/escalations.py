"""Handoffs the agent proposes. A user approves one before Linear sees it."""

import logging
from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from kb_api import linear
from kb_api.audit import audit
from kb_api.auth import (
    AUTH_ERRORS,
    ErrorBody,
    InternalCaller,
    Principal,
    require_internal,
)
from kb_api.db import EscalationRow, LiveSessionRow, ProductRow, utcnow
from kb_api.integrations import (
    NOT_CONFIGURED,
    Clock,
    Db,
    Http,
    User,
    authorization_for,
    load_connection,
)
from kb_api.linear import LinearError
from kb_api.linear_secrets import Config
from kb_api.redact import redact

router = APIRouter(tags=["escalations"], responses=AUTH_ERRORS)
log = logging.getLogger(__name__)

TITLE_LIMIT = 120
# Each proposal is a card the user must read, so one session carries only a few.
MAX_PROPOSALS_PER_SESSION = 3
AGENT = "agent"
# A creating row this idle lost its request, so approve may claim it again.
CREATING_LEASE = timedelta(minutes=2)

NOT_CONNECTED: dict[int | str, dict[str, object]] = {
    409: {"model": ErrorBody, "description": "Linear is not connected for this org"}
}
NOT_FOUND: dict[int | str, dict[str, object]] = {
    404: {"model": ErrorBody, "description": "No such escalation in this org"}
}
TOO_MANY: dict[int | str, dict[str, object]] = {
    429: {
        "model": ErrorBody,
        "description": (
            "The session already has the maximum number of handoff proposals"
        ),
    }
}


class Proposal(BaseModel):
    room: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    summary: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]
    reason: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
    ]
    transcript: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=6000)
    ] = ""


class Escalation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    body: str
    status: str
    issue_identifier: str | None
    issue_url: str | None


def title_of(summary: str) -> str:
    line = " ".join(summary.split())
    return line if len(line) <= TITLE_LIMIT else f"{line[: TITLE_LIMIT - 1]}…"


def body_of(product_name: str, proposal: Proposal) -> str:
    parts = [
        proposal.summary,
        f"Product: {product_name}",
        f"Reason for handoff: {proposal.reason}",
    ]
    if proposal.transcript:
        quoted = "\n".join(f"> {line}" for line in proposal.transcript.splitlines())
        parts.append(f"Recent conversation:\n{quoted}")
    return "\n\n".join(parts)


async def owned_escalation(db: AsyncSession, org_id: str, id: UUID) -> EscalationRow:
    row = await db.scalar(
        select(EscalationRow).where(
            EscalationRow.id == id, EscalationRow.org_id == org_id
        )
    )
    if row is None:
        raise HTTPException(404, "escalation not found")
    return row


@router.post(
    "/internal/escalations",
    status_code=201,
    responses={
        404: {"model": ErrorBody, "description": "No such session"},
        **NOT_CONNECTED,
        **TOO_MANY,
        **NOT_CONFIGURED,
    },
)
async def propose_escalation(
    body: Proposal,
    _: Annotated[InternalCaller, Depends(require_internal)],
    db: Db,
    config: Config,
) -> Escalation:
    session = await db.scalar(
        select(LiveSessionRow).where(LiveSessionRow.room == body.room)
    )
    if session is None:
        raise HTTPException(404, "session not found")
    if await load_connection(db, session.org_id) is None:
        raise HTTPException(409, "Linear is not connected")
    # Every status counts, so a dismissed proposal still uses its slot.
    proposed = await db.scalar(
        select(func.count())
        .select_from(EscalationRow)
        .where(EscalationRow.room == session.room)
    )
    if (proposed or 0) >= MAX_PROPOSALS_PER_SESSION:
        raise HTTPException(429, "too many handoffs proposed in this session")
    product = await db.get(ProductRow, session.product_id)
    assert product is not None  # the session row cascades with its product
    row = EscalationRow(
        org_id=session.org_id,
        product_id=session.product_id,
        room=session.room,
        title=title_of(redact(body.summary)),
        body=redact(body_of(product.name, body)),
        status="proposed",
    )
    db.add(row)
    await db.flush()
    audit(
        db,
        Principal(org_id=row.org_id, actor=AGENT, user_id=None),
        "escalation.propose",
        f"escalation:{row.id}",
        {"room": row.room},
    )
    await db.commit()
    return Escalation.model_validate(row)


async def move(
    db: AsyncSession,
    row: EscalationRow,
    was: str,
    to: str,
    *,
    idle_for: timedelta | None = None,
    **values: str,
) -> bool:
    """Move the row from `was` to `to`. False when another request moved it first.

    With `idle_for`, the row must also be unchanged for that long.
    The caller commits, so an audit row can join the same transaction."""
    conditions = [EscalationRow.id == row.id, EscalationRow.status == was]
    if idle_for is not None:
        conditions.append(EscalationRow.updated_at <= utcnow() - idle_for)
    moved = await db.execute(
        update(EscalationRow)
        .where(*conditions)
        .values(status=to, updated_at=utcnow(), **values)
        .returning(EscalationRow.id)
        # The refresh below reloads the row, so skip evaluating the clause here.
        .execution_options(synchronize_session=False)
    )
    changed = moved.scalar_one_or_none() is not None
    await db.refresh(row)
    return changed


@router.post(
    "/escalations/{escalation_id}/approve",
    responses={
        **NOT_FOUND,
        409: {
            "model": ErrorBody,
            "description": (
                "Dismissed, in progress, or no Linear. A creating escalation"
                " idle for two minutes can be approved again"
            ),
        },
        502: {"model": ErrorBody, "description": "Linear did not create the issue"},
        **NOT_CONFIGURED,
    },
)
async def approve_escalation(
    escalation_id: UUID,
    principal: User,
    db: Db,
    config: Config,
    http: Http,
    clock: Clock,
) -> Escalation:
    row = await owned_escalation(db, principal.org_id, escalation_id)
    if row.status == "created":
        return Escalation.model_validate(row)
    # Only one request wins the claim, so a double click creates one issue.
    # A creating row past its lease lost its request, and the claim renews it.
    claimed = await move(db, row, "proposed", "creating") or await move(
        db, row, "creating", "creating", idle_for=CREATING_LEASE
    )
    await db.commit()
    if not claimed:
        if row.status == "created":
            return Escalation.model_validate(row)
        raise HTTPException(409, f"the escalation is {row.status}")
    connection = await load_connection(db, principal.org_id)
    try:
        if connection is None:
            raise HTTPException(409, "Linear is not connected")
        authorization = await authorization_for(db, http, config, connection, clock())
        issue = await linear.create_issue(
            http, authorization, connection.team_id, row.title, row.body
        )
    except (HTTPException, LinearError) as exc:
        await move(db, row, "creating", "proposed")
        if isinstance(exc, LinearError):
            log.warning("Linear issueCreate failed for %s: %s", row.id, exc)
            audit(
                db,
                principal,
                "escalation.approve_failed",
                f"escalation:{row.id}",
                {"error": str(exc)},
            )
        await db.commit()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(502, "Linear did not create the issue") from exc
    await move(
        db,
        row,
        "creating",
        "created",
        issue_identifier=issue.identifier,
        issue_url=issue.url,
    )
    audit(
        db,
        principal,
        "escalation.approve",
        f"escalation:{row.id}",
        {"identifier": issue.identifier},
    )
    await db.commit()
    return Escalation.model_validate(row)


@router.post(
    "/escalations/{escalation_id}/dismiss",
    responses={
        **NOT_FOUND,
        409: {"model": ErrorBody, "description": "The issue was already created"},
    },
)
async def dismiss_escalation(
    escalation_id: UUID, principal: User, db: Db
) -> Escalation:
    row = await owned_escalation(db, principal.org_id, escalation_id)
    if await move(db, row, "proposed", "dismissed"):
        audit(db, principal, "escalation.dismiss", f"escalation:{row.id}")
        await db.commit()
    if row.status != "dismissed":
        raise HTTPException(409, f"the escalation is {row.status}")
    return Escalation.model_validate(row)
