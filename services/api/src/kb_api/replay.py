"""What happened in a live session: the agent records turns, people replay them."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kb_api.auth import (
    AUTH_ERRORS,
    ErrorBody,
    InternalCaller,
    Principal,
    get_principal,
    require_internal,
)
from kb_api.db import AuditRow, EscalationRow, LiveSessionRow, TurnRow, get_db
from kb_api.redact import redact
from kb_api.sessions import LiveSession

router = APIRouter(tags=["sessions"], responses=AUTH_ERRORS)

NOT_FOUND: dict[int | str, dict[str, object]] = {
    404: {"model": ErrorBody, "description": "No such session in this org"}
}
# The audit detail that says most about each desktop event, first match wins.
DETAIL_KEYS = ("action", "outcome", "error", "decision", "by")

Short = Annotated[str, StringConstraints(max_length=500)]


class SearchedPassage(BaseModel):
    id: Short
    title: Short
    source: Short
    score: float


class Search(BaseModel):
    query: Annotated[str, StringConstraints(max_length=2000)]
    passages: Annotated[list[SearchedPassage], Field(max_length=20)]
    abstained: bool
    duration_ms: Annotated[int, Field(ge=0)]


class TurnRecord(BaseModel):
    """One turn, as the agent reports it."""

    room: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    role: Literal["user", "assistant"]
    text: Annotated[str, StringConstraints(max_length=20000)]
    started_at: datetime
    ended_at: datetime
    searches: Annotated[list[Search], Field(max_length=10)] = []
    cited: Annotated[list[Short], Field(max_length=20)] = []
    latency: Annotated[
        dict[Short, Annotated[int, Field(ge=0)]], Field(max_length=20)
    ] = {}
    image_tokens: Annotated[int, Field(ge=0)] | None = None


class Citation(BaseModel):
    id: str
    title: str
    source: str


class Turn(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    text: str
    started_at: datetime
    ended_at: datetime
    searches: list[Search]
    citations: list[Citation]
    latency: dict[str, int]
    image_tokens: int | None


class DesktopAction(BaseModel):
    event: str
    at: datetime
    task: str | None
    detail: str


class Handoff(BaseModel):
    title: str
    status: str
    issue_identifier: str | None
    issue_url: str | None
    created_at: datetime


class SessionSummary(LiveSession):
    ended_at: datetime | None
    turn_count: int
    action_count: int
    handoff_count: int


class Replay(SessionSummary):
    turns: list[Turn]
    actions: list[DesktopAction]
    handoffs: list[Handoff]


def target_of(session_id: UUID) -> str:
    return f"session:{session_id}"


@router.post(
    "/internal/turns",
    status_code=204,
    include_in_schema=False,
    responses={404: {"model": ErrorBody, "description": "No such session"}},
)
async def record_turn(
    body: TurnRecord,
    _: Annotated[InternalCaller, Depends(require_internal)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    session = await db.scalar(
        select(LiveSessionRow).where(LiveSessionRow.room == body.room)
    )
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    searches = [
        search.model_copy(update={"query": redact(search.query)})
        for search in body.searches
    ]
    db.add(
        TurnRow(
            session_id=session.id,
            role=body.role,
            text=redact(body.text),
            started_at=body.started_at,
            ended_at=body.ended_at,
            searches=[search.model_dump() for search in searches],
            cited=body.cited,
            latency=body.latency,
            image_tokens=body.image_tokens,
        )
    )
    await db.commit()


async def summarize(
    db: AsyncSession, sessions: list[LiveSessionRow]
) -> list[SessionSummary]:
    ids = [row.id for row in sessions]
    turns = {
        session_id: (count, last)
        for session_id, count, last in await db.execute(
            select(TurnRow.session_id, func.count(), func.max(TurnRow.ended_at))
            .where(TurnRow.session_id.in_(ids))
            .group_by(TurnRow.session_id)
        )
    }
    actions = dict(
        (
            await db.execute(
                select(AuditRow.target, func.count())
                .where(
                    AuditRow.action == "desktop.performed",
                    AuditRow.target.in_([target_of(i) for i in ids]),
                )
                .group_by(AuditRow.target)
            )
        ).all()
    )
    handoffs = dict(
        (
            await db.execute(
                select(EscalationRow.room, func.count())
                .where(EscalationRow.room.in_([row.room for row in sessions]))
                .group_by(EscalationRow.room)
            )
        ).all()
    )
    summaries: list[SessionSummary] = []
    for row in sessions:
        count, last = turns.get(row.id, (0, None))
        summaries.append(
            SessionSummary(
                **LiveSession.model_validate(row).model_dump(),
                ended_at=last,
                turn_count=count,
                action_count=actions.get(target_of(row.id), 0),
                handoff_count=handoffs.get(row.room, 0),
            )
        )
    return summaries


@router.get("/sessions")
async def list_sessions(
    principal: Annotated[Principal, Depends(get_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    product_id: UUID | None = None,
) -> list[SessionSummary]:
    query = select(LiveSessionRow).where(LiveSessionRow.org_id == principal.org_id)
    if product_id is not None:
        query = query.where(LiveSessionRow.product_id == product_id)
    rows = await db.scalars(query.order_by(LiveSessionRow.created_at.desc()).limit(100))
    return await summarize(db, list(rows))


def detail_of(details: dict[str, Any]) -> str:
    for key in DETAIL_KEYS:
        if key in details:
            return redact(str(details[key]))
    return ""


@router.get("/sessions/{session_id}", responses=NOT_FOUND)
async def get_replay(
    session_id: UUID,
    principal: Annotated[Principal, Depends(get_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Replay:
    row = await db.scalar(
        select(LiveSessionRow).where(
            LiveSessionRow.id == session_id, LiveSessionRow.org_id == principal.org_id
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    [summary] = await summarize(db, [row])
    turn_rows = list(
        await db.scalars(
            select(TurnRow)
            .where(TurnRow.session_id == row.id)
            .order_by(TurnRow.started_at, TurnRow.created_at)
        )
    )
    found = {
        passage["id"]: passage
        for turn in turn_rows
        for search in turn.searches
        for passage in search["passages"]
    }
    turns = [
        Turn(
            id=turn.id,
            role=turn.role,  # type: ignore[arg-type]
            text=turn.text,
            started_at=turn.started_at,
            ended_at=turn.ended_at,
            searches=[Search.model_validate(search) for search in turn.searches],
            citations=[
                Citation(
                    id=id,
                    title=found.get(id, {}).get("title", id),
                    source=found.get(id, {}).get("source", ""),
                )
                for id in turn.cited
            ],
            latency=turn.latency,
            image_tokens=turn.image_tokens,
        )
        for turn in turn_rows
    ]
    audits = await db.scalars(
        select(AuditRow)
        .where(
            AuditRow.org_id == principal.org_id,
            AuditRow.target == target_of(row.id),
            AuditRow.action.like("desktop.%"),
        )
        .order_by(AuditRow.at)
    )
    actions = [
        DesktopAction(
            event=audit.action.removeprefix("desktop."),
            at=audit.at,
            task=audit.details.get("task"),
            detail=detail_of(audit.details),
        )
        for audit in audits
    ]
    escalations = await db.scalars(
        select(EscalationRow)
        .where(EscalationRow.org_id == principal.org_id, EscalationRow.room == row.room)
        .order_by(EscalationRow.created_at)
    )
    handoffs = [
        Handoff(
            title=escalation.title,
            status=escalation.status,
            issue_identifier=escalation.issue_identifier,
            issue_url=escalation.issue_url,
            created_at=escalation.created_at,
        )
        for escalation in escalations
    ]
    return Replay(
        **summary.model_dump(), turns=turns, actions=actions, handoffs=handoffs
    )
