from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from kb_api.db import EscalationRow, LiveSessionRow
from kb_api.settings import load_settings
from sqlalchemy import Engine
from sqlalchemy.orm import Session

PRODUCT = {
    "name": "Acme",
    "description": "Acme helps customers reset passwords.",
    "tone": "calm and brief",
    "refusal_rules": "Do not invent a refund policy.",
}
AGENT = {"x-internal-token": "agent-secret"}
Headers = Callable[..., dict[str, str]]


@dataclass
class Live:
    id: str
    room: str
    product_id: str


@pytest.fixture(autouse=True)
def internal_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "agent-secret")
    load_settings.cache_clear()


def start(http: TestClient, engine: Engine, headers: dict[str, str], org: str) -> Live:
    """A live session as POST /sessions records it, without a LiveKit server."""
    product = http.post("/products", json=PRODUCT, headers=headers).json()["id"]
    room = f"kb-{uuid4()}"
    with Session(engine) as db:
        row = LiveSessionRow(
            org_id=org, product_id=UUID(product), room=room, user_id="user-a"
        )
        db.add(row)
        db.commit()
        return Live(id=str(row.id), room=room, product_id=product)


@pytest.fixture
def live(http: TestClient, sync_engine: Engine, as_user: Headers) -> Live:
    return start(http, sync_engine, as_user(), "org-a")


def turn(room: str, role: str, started: int, **fields: object) -> dict[str, object]:
    return {
        "room": room,
        "role": role,
        "text": "hello",
        "started_at": f"2026-11-03T10:00:{started:02d}Z",
        "ended_at": f"2026-11-03T10:00:{started + 1:02d}Z",
        **fields,
    }


def record(http: TestClient, body: dict[str, object]) -> int:
    return http.post("/internal/turns", json=body, headers=AGENT).status_code


def test_the_replay_lists_turns_in_the_order_they_were_said(
    http: TestClient, live: Live, as_user: Headers
) -> None:
    passage = {"id": "p1", "title": "Reset a password", "source": "a.md", "score": 0.91}
    search = {
        "query": "reset password",
        "passages": [passage],
        "abstained": False,
        "duration_ms": 180,
    }
    answer = turn(
        live.room,
        "assistant",
        5,
        text="Open Settings, then Security.",
        searches=[search],
        cited=["p1"],
        latency={"llm_ttft_ms": 420, "tts_ttfb_ms": 90},
        image_tokens=258,
    )
    question = turn(live.room, "user", 2, text="How do I reset my password?")
    # The agent posts without waiting, so the answer can arrive first.
    assert record(http, answer) == 204
    assert record(http, question) == 204

    replay = http.get(f"/sessions/{live.id}", headers=as_user()).json()

    assert [t["role"] for t in replay["turns"]] == ["user", "assistant"]
    first, second = replay["turns"]
    assert first["text"] == "How do I reset my password?"
    assert second["searches"] == [search]
    assert second["citations"] == [
        {"id": "p1", "title": "Reset a password", "source": "a.md"}
    ]
    assert second["latency"] == {"llm_ttft_ms": 420, "tts_ttfb_ms": 90}
    assert second["image_tokens"] == 258
    assert replay["turn_count"] == 2
    assert replay["ended_at"].startswith("2026-11-03T10:00:06")


def test_the_replay_has_the_desktop_steps_and_handoffs_of_that_session(
    http: TestClient, sync_engine: Engine, live: Live, as_user: Headers
) -> None:
    steps = [
        ("proposed", {"task": "t1", "action": "types 'a@b.co'", "proposal": "p"}),
        ("approved", {"task": "t1", "decision": "once", "proposal": "p"}),
        ("performed", {"task": "t1", "action": "Click Save"}),
        ("ended", {"task": "t1", "outcome": "done"}),
    ]
    for event, details in steps:
        body = {"room": live.room, "event": event, "details": details}
        http.post("/internal/desktop-actions", json=body, headers=AGENT)
    with Session(sync_engine) as db:
        db.add(
            EscalationRow(
                org_id="org-a",
                product_id=UUID(live.product_id),
                room=live.room,
                title="Cannot reset password",
                body="b",
                status="proposed",
            )
        )
        db.commit()

    replay = http.get(f"/sessions/{live.id}", headers=as_user()).json()

    assert [(a["event"], a["task"], a["detail"]) for a in replay["actions"]] == [
        ("proposed", "t1", "types '[email]'"),
        ("approved", "t1", "once"),
        ("performed", "t1", "Click Save"),
        ("ended", "t1", "done"),
    ]
    assert [(h["title"], h["status"]) for h in replay["handoffs"]] == [
        ("Cannot reset password", "proposed")
    ]
    [listed] = http.get("/sessions", headers=as_user()).json()
    assert (listed["action_count"], listed["handoff_count"]) == (1, 1)


def test_stored_text_has_no_emails_phones_or_card_numbers(
    http: TestClient, live: Live, as_user: Headers, rows
) -> None:
    said = "Mail ann@example.com or call +1 415 555 0100, card 4242 4242 4242 4242."
    search = {
        "query": "refund for ann@example.com",
        "passages": [],
        "abstained": True,
        "duration_ms": 5,
    }

    record(http, turn(live.room, "user", 1, text=said, searches=[search]))

    [stored] = rows("turns")
    assert stored["text"] == "Mail [email] or call [phone], card [card]."
    [shown] = http.get(f"/sessions/{live.id}", headers=as_user()).json()["turns"]
    assert shown["searches"][0]["query"] == "refund for [email]"


def test_a_session_with_no_turns_is_listed_and_replayed_empty(
    http: TestClient, live: Live, as_user: Headers
) -> None:
    [listed] = http.get("/sessions", headers=as_user()).json()
    replay = http.get(f"/sessions/{live.id}", headers=as_user()).json()

    assert listed["id"] == live.id
    assert (listed["turn_count"], listed["ended_at"]) == (0, None)
    assert (replay["turns"], replay["actions"], replay["handoffs"]) == ([], [], [])


def test_another_org_sees_neither_the_session_nor_its_turns(
    http: TestClient, live: Live, as_user: Headers
) -> None:
    record(http, turn(live.room, "user", 1))
    other = as_user(user="user-b", org="org-b")

    assert http.get(f"/sessions/{live.id}", headers=other).status_code == 404
    assert http.get("/sessions", headers=other).json() == []
    assert http.get(f"/sessions/{uuid4()}", headers=as_user()).status_code == 404


def test_the_list_filters_by_product(
    http: TestClient, sync_engine: Engine, live: Live, as_user: Headers
) -> None:
    second = start(http, sync_engine, as_user(), "org-a")

    listed = http.get(
        "/sessions", params={"product_id": second.product_id}, headers=as_user()
    ).json()

    assert [item["id"] for item in listed] == [second.id]


def test_only_the_agent_records_turns(
    http: TestClient, live: Live, as_user: Headers
) -> None:
    body = turn(live.room, "user", 1)

    assert http.post("/internal/turns", json=body).status_code == 401
    assert http.post("/internal/turns", json=body, headers=as_user()).status_code == 401
    wrong = {"x-internal-token": "nope"}
    assert http.post("/internal/turns", json=body, headers=wrong).status_code == 401


@pytest.mark.parametrize(
    ("change", "status"),
    [
        ({"room": "kb-nothing"}, 404),
        ({"role": "system"}, 422),
        ({"text": "x" * 20001}, 422),
        ({"latency": {"llm_ttft_ms": -1}}, 422),
        ({"cited": [f"p{i}" for i in range(21)]}, 422),
    ],
)
def test_a_turn_for_no_session_or_out_of_shape_is_refused(
    http: TestClient, live: Live, rows, change: dict[str, object], status: int
) -> None:
    assert record(http, {**turn(live.room, "user", 1), **change}) == status
    assert rows("turns") == []
