import base64
import json
from collections.abc import Callable
from datetime import timedelta
from urllib.parse import parse_qs, parse_qsl, urlparse
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from kb_api.db import LiveSessionRow, utcnow
from kb_api.linear import GRAPHQL_URL, REVOKE_URL, TOKEN_URL, get_linear_http
from kb_api.linear_secrets import STATE_TTL_SECONDS
from kb_api.sessions import get_clock
from kb_api.settings import load_settings
from sqlalchemy import DateTime, Engine, Uuid, bindparam, text
from sqlalchemy.orm import Session

KEY = base64.b64encode(bytes(range(32))).decode()
INTERNAL = "internal-test-token"
NOW = 1_800_000_000.0
PRODUCT = {
    "name": "Acme",
    "description": "Acme helps customers reset passwords.",
    "tone": "calm and brief",
    "refusal_rules": "Do not invent a refund policy.",
}

Headers = Callable[..., dict[str, str]]


class FakeLinear:
    """Stands in for api.linear.app. It records what the API sent."""

    def __init__(self) -> None:
        self.forms: list[dict[str, str]] = []
        self.revoked: list[str] = []
        self.issues: list[dict[str, object]] = []
        self.authorizations: list[str] = []
        self.token_status = 200
        self.issue_failures = 0
        self.expires_in = 86399
        self.teams = [{"id": "team-1", "key": "ENG", "name": "Engineering"}]

    def handle(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == TOKEN_URL:
            form = dict(parse_qsl(request.content.decode()))
            self.forms.append(form)
            rotated = len(self.forms)
            return httpx.Response(
                self.token_status,
                json={
                    "access_token": f"access-{rotated}",
                    "refresh_token": f"refresh-{rotated}",
                    "expires_in": self.expires_in,
                    "token_type": "Bearer",
                },
            )
        if url == REVOKE_URL:
            self.revoked.append(dict(parse_qsl(request.content.decode()))["token"])
            return httpx.Response(200)
        assert url == GRAPHQL_URL
        self.authorizations.append(request.headers["authorization"])
        body = json.loads(request.content)
        if "issueCreate" in body["query"]:
            if self.issue_failures:
                self.issue_failures -= 1
                return httpx.Response(200, json={"errors": [{"message": "boom"}]})
            self.issues.append(body["variables"]["input"])
            number = len(self.issues)
            return httpx.Response(
                200,
                json={
                    "data": {
                        "issueCreate": {
                            "success": True,
                            "issue": {
                                "identifier": f"ENG-{number}",
                                "url": f"https://linear.app/acme/issue/ENG-{number}",
                            },
                        }
                    }
                },
            )
        return httpx.Response(
            200,
            json={
                "data": {
                    "organization": {"name": "Acme Inc"},
                    "teams": {"nodes": self.teams},
                }
            },
        )


@pytest.fixture
def linear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINEAR_CLIENT_ID", "client-id")
    monkeypatch.setenv("LINEAR_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("LINEAR_TOKEN_KEY", KEY)
    monkeypatch.setenv("INTERNAL_API_TOKEN", INTERNAL)
    load_settings.cache_clear()


@pytest.fixture
def linear(linear_env: None, http: TestClient) -> FakeLinear:
    from kb_api.main import app

    fake = FakeLinear()
    client = httpx.AsyncClient(transport=httpx.MockTransport(fake.handle))
    app.dependency_overrides[get_linear_http] = lambda: client
    set_clock(NOW)
    return fake


def set_clock(now: float) -> None:
    from kb_api.main import app

    app.dependency_overrides[get_clock] = lambda: lambda: now


def connect(http: TestClient, headers: dict[str, str]):
    url = http.get("/integrations/linear/connect", headers=headers).json()["url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    return http.post(
        "/integrations/linear/callback",
        json={"code": "the-code", "state": state},
        headers=headers,
    )


def propose(http: TestClient, room: str, **fields: str):
    body = {
        "room": room,
        "summary": "Customer cannot reset their password",
        "reason": "The docs do not cover SSO accounts",
        "transcript": "User: my reset email never arrives",
        **fields,
    }
    return http.post(
        "/internal/escalations", json=body, headers={"x-internal-token": INTERNAL}
    )


def stuck_creating(sync_engine: Engine, id: str, idle: timedelta) -> None:
    """Leave the escalation as a request that died after its claim would."""
    update = text(
        "UPDATE escalations SET status = 'creating', updated_at = :at WHERE id = :id"
    ).bindparams(
        bindparam("at", type_=DateTime(timezone=True)), bindparam("id", type_=Uuid())
    )
    with sync_engine.begin() as connection:
        connection.execute(update, {"at": utcnow() - idle, "id": UUID(id)})


@pytest.fixture
def room(http: TestClient, sync_engine: Engine, as_user: Headers) -> str:
    """A live session of org-a's product, as POST /sessions would record it."""
    product = http.post("/products", json=PRODUCT, headers=as_user()).json()["id"]
    name = f"kb-{uuid4()}"
    with Session(sync_engine) as db:
        db.add(
            LiveSessionRow(
                org_id="org-a", product_id=UUID(product), room=name, user_id="user-a"
            )
        )
        db.commit()
    return name


def test_without_linear_settings_every_route_says_what_to_set(
    http: TestClient, as_user: Headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LINEAR_CLIENT_ID", "replace-me")
    monkeypatch.setenv("LINEAR_TOKEN_KEY", KEY)
    load_settings.cache_clear()

    status = http.get("/integrations/linear", headers=as_user())
    connect_response = http.get("/integrations/linear/connect", headers=as_user())

    assert status.json() == {
        "enabled": False,
        "connected": False,
        "workspace_name": None,
        "team_name": None,
        "team_key": None,
    }
    assert connect_response.status_code == 503
    assert "LINEAR_CLIENT_ID" in connect_response.json()["detail"]


def test_a_malformed_token_key_is_a_503(
    http: TestClient,
    as_user: Headers,
    linear_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LINEAR_TOKEN_KEY", "too-short")
    load_settings.cache_clear()

    response = http.get("/integrations/linear/connect", headers=as_user())

    assert response.status_code == 503
    assert "LINEAR_TOKEN_KEY" in response.json()["detail"]


def test_connect_returns_the_linear_authorize_url(
    http: TestClient, as_user: Headers, linear: FakeLinear
) -> None:
    response = http.get("/integrations/linear/connect", headers=as_user())

    url = urlparse(response.json()["url"])
    query = parse_qs(url.query)
    assert f"{url.scheme}://{url.netloc}{url.path}" == (
        "https://linear.app/oauth/authorize"
    )
    assert query["client_id"] == ["client-id"]
    assert query["redirect_uri"] == [
        "http://localhost:3000/api/integrations/linear/callback"
    ]
    assert query["response_type"] == ["code"]
    assert query["scope"] == ["read,issues:create"]
    assert query["state"][0]


def test_callback_stores_encrypted_tokens_and_the_workspace(
    http: TestClient, as_user: Headers, linear: FakeLinear, rows
) -> None:
    response = connect(http, as_user())

    assert response.status_code == 200
    assert response.json() == {
        "enabled": True,
        "connected": True,
        "workspace_name": "Acme Inc",
        "team_name": "Engineering",
        "team_key": "ENG",
    }
    [form] = linear.forms
    assert form == {
        "grant_type": "authorization_code",
        "code": "the-code",
        "redirect_uri": "http://localhost:3000/api/integrations/linear/callback",
        "client_id": "client-id",
        "client_secret": "client-secret",
    }
    assert linear.authorizations == ["Bearer access-1"]
    [row] = rows("linear_connections")
    assert row["org_id"] == "org-a"
    assert row["team_id"] == "team-1"
    assert row["connected_by"] == "user-a"
    assert row["expires_at"] == int(NOW) + 86399
    assert isinstance(row["access_token"], bytes)
    assert b"access-1" not in row["access_token"]
    assert isinstance(row["refresh_token"], bytes)
    assert b"refresh-1" not in row["refresh_token"]
    assert [r["action"] for r in rows("audit_log")] == ["linear.connect"]
    other = http.get("/integrations/linear", headers=as_user(user="u", org="org-b"))
    assert other.json()["connected"] is False


def test_connecting_again_replaces_the_connection(
    http: TestClient, as_user: Headers, linear: FakeLinear, rows
) -> None:
    connect(http, as_user())
    linear.teams = [{"id": "team-9", "key": "OPS", "name": "Operations"}]

    again = connect(http, as_user(user="user-b"))

    assert again.json()["team_key"] == "OPS"
    [row] = rows("linear_connections")
    assert (row["team_id"], row["connected_by"]) == ("team-9", "user-b")


@pytest.mark.parametrize(
    "caller",
    [{"user": "user-b", "org": "org-a"}, {"user": "user-a", "org": "org-b"}],
)
def test_a_state_only_works_for_the_user_and_org_that_asked(
    http: TestClient, as_user: Headers, linear: FakeLinear, rows, caller
) -> None:
    url = http.get("/integrations/linear/connect", headers=as_user()).json()["url"]
    state = parse_qs(urlparse(url).query)["state"][0]

    response = http.post(
        "/integrations/linear/callback",
        json={"code": "c", "state": state},
        headers=as_user(**caller),
    )

    assert response.status_code == 400
    assert linear.forms == []
    assert rows("linear_connections") == []


def test_a_tampered_or_expired_state_is_a_400(
    http: TestClient, as_user: Headers, linear: FakeLinear, rows
) -> None:
    url = http.get("/integrations/linear/connect", headers=as_user()).json()["url"]
    state = parse_qs(urlparse(url).query)["state"][0]

    def call(value: str):
        return http.post(
            "/integrations/linear/callback",
            json={"code": "c", "state": value},
            headers=as_user(),
        )

    assert call(state[:-3] + "AAA").status_code == 400
    assert call("nonsense").status_code == 400
    set_clock(NOW + STATE_TTL_SECONDS + 1)
    expired = call(state)
    assert expired.status_code == 400
    assert expired.json() == {"detail": "invalid or expired state"}
    assert linear.forms == []
    assert rows("linear_connections") == []


def test_a_state_works_once(
    http: TestClient, as_user: Headers, linear: FakeLinear
) -> None:
    url = http.get("/integrations/linear/connect", headers=as_user()).json()["url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    body = {"code": "c", "state": state}

    first = http.post("/integrations/linear/callback", json=body, headers=as_user())
    replay = http.post("/integrations/linear/callback", json=body, headers=as_user())

    assert first.status_code == 200
    assert replay.status_code == 400
    assert len(linear.forms) == 1


def test_a_refused_code_stores_nothing(
    http: TestClient, as_user: Headers, linear: FakeLinear, rows
) -> None:
    linear.token_status = 400

    response = connect(http, as_user())

    assert response.status_code == 502
    assert "the-code" not in response.text
    assert rows("linear_connections") == []


def test_a_workspace_without_teams_is_not_connected(
    http: TestClient, as_user: Headers, linear: FakeLinear, rows
) -> None:
    linear.teams = []

    assert connect(http, as_user()).status_code == 502
    assert rows("linear_connections") == []


def test_disconnect_revokes_deletes_and_stays_in_its_org(
    http: TestClient, as_user: Headers, linear: FakeLinear, rows
) -> None:
    connect(http, as_user())
    connect(http, as_user(user="user-b", org="org-b"))

    other = http.delete("/integrations/linear", headers=as_user(user="u", org="org-c"))
    assert other.status_code == 204
    assert len(rows("linear_connections")) == 2

    gone = http.delete("/integrations/linear", headers=as_user())

    assert gone.status_code == 204
    assert linear.revoked == ["refresh-1"]
    assert [r["org_id"] for r in rows("linear_connections")] == ["org-b"]
    assert "linear.disconnect" in [r["action"] for r in rows("audit_log")]
    assert http.delete("/integrations/linear", headers=as_user()).status_code == 204


def test_the_agent_cannot_propose_without_the_internal_token(
    http: TestClient, linear: FakeLinear, room: str, as_user: Headers
) -> None:
    connect(http, as_user())
    body = {"room": room, "summary": "s", "reason": "r"}

    assert http.post("/internal/escalations", json=body).status_code == 401
    wrong = http.post(
        "/internal/escalations", json=body, headers={"x-internal-token": "nope"}
    )
    assert wrong.status_code == 401
    as_a_user = http.post("/internal/escalations", json=body, headers=as_user())
    assert as_a_user.status_code == 401


def test_without_a_connection_or_a_session_nothing_is_proposed(
    http: TestClient, linear: FakeLinear, room: str, rows
) -> None:
    assert propose(http, room).status_code == 409
    assert propose(http, "kb-unknown").status_code == 404
    assert rows("escalations") == []


def test_a_proposal_is_redacted_scoped_and_audited(
    http: TestClient, linear: FakeLinear, room: str, as_user: Headers, rows
) -> None:
    connect(http, as_user())

    response = propose(
        http,
        room,
        summary="Ana (ana@example.com) cannot pay",
        transcript="User: my card is 4111 1111 1111 1111\nUser: call +1 415 555 0132",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "proposed"
    assert body["title"] == "Ana ([email]) cannot pay"
    assert "Product: Acme" in body["body"]
    assert "Reason for handoff: The docs do not cover SSO accounts" in body["body"]
    assert "> User: my card is [card]" in body["body"]
    assert "> User: call [phone]" in body["body"]
    [stored] = rows("escalations")
    assert stored["org_id"] == "org-a"
    assert stored["room"] == room
    assert "ana@example.com" not in stored["body"] + stored["title"]
    assert linear.issues == []
    audit = [r for r in rows("audit_log") if r["action"] == "escalation.propose"]
    assert [(r["org_id"], r["actor"]) for r in audit] == [("org-a", "agent")]


def test_a_long_summary_makes_a_short_title(
    http: TestClient, linear: FakeLinear, room: str, as_user: Headers
) -> None:
    connect(http, as_user())

    title = propose(http, room, summary="word " * 100).json()["title"]

    assert len(title) == 120
    assert title.endswith("…")


def test_approve_creates_the_issue_once(
    http: TestClient, linear: FakeLinear, room: str, as_user: Headers, rows
) -> None:
    connect(http, as_user())
    escalation = propose(http, room).json()
    url = f"/escalations/{escalation['id']}/approve"

    first = http.post(url, headers=as_user())
    second = http.post(url, headers=as_user())

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["status"] == "created"
    assert first.json()["issue_identifier"] == "ENG-1"
    assert first.json()["issue_url"] == "https://linear.app/acme/issue/ENG-1"
    [issue] = linear.issues
    assert issue == {
        "teamId": "team-1",
        "title": escalation["title"],
        "description": escalation["body"],
    }
    assert linear.authorizations[-1] == "Bearer access-1"
    actions = [r["action"] for r in rows("audit_log")]
    assert actions.count("escalation.approve") == 1


def test_another_orgs_escalation_is_a_404(
    http: TestClient, linear: FakeLinear, room: str, as_user: Headers
) -> None:
    connect(http, as_user())
    connect(http, as_user(user="user-b", org="org-b"))
    escalation = propose(http, room).json()
    other = as_user(user="user-b", org="org-b")

    for action in ("approve", "dismiss"):
        response = http.post(f"/escalations/{escalation['id']}/{action}", headers=other)
        assert response.status_code == 404
    assert (
        http.post(f"/escalations/{uuid4()}/approve", headers=as_user()).status_code
        == 404
    )
    assert linear.issues == []


def test_dismiss_never_calls_linear_and_blocks_approval(
    http: TestClient, linear: FakeLinear, room: str, as_user: Headers, rows
) -> None:
    connect(http, as_user())
    calls_before = len(linear.authorizations)
    escalation = propose(http, room).json()
    base = f"/escalations/{escalation['id']}"

    dismissed = http.post(f"{base}/dismiss", headers=as_user())
    again = http.post(f"{base}/dismiss", headers=as_user())
    approve = http.post(f"{base}/approve", headers=as_user())

    assert dismissed.json()["status"] == again.json()["status"] == "dismissed"
    assert approve.status_code == 409
    assert linear.issues == []
    assert len(linear.authorizations) == calls_before
    actions = [r["action"] for r in rows("audit_log")]
    assert actions.count("escalation.dismiss") == 1


def test_a_created_escalation_cannot_be_dismissed(
    http: TestClient, linear: FakeLinear, room: str, as_user: Headers
) -> None:
    connect(http, as_user())
    base = f"/escalations/{propose(http, room).json()['id']}"
    http.post(f"{base}/approve", headers=as_user())

    response = http.post(f"{base}/dismiss", headers=as_user())

    assert response.status_code == 409
    assert http.post(f"{base}/approve", headers=as_user()).json()["status"] == "created"


def test_a_failed_issue_create_can_be_retried(
    http: TestClient, linear: FakeLinear, room: str, as_user: Headers, rows
) -> None:
    connect(http, as_user())
    base = f"/escalations/{propose(http, room).json()['id']}"
    linear.issue_failures = 1

    failed = http.post(f"{base}/approve", headers=as_user())

    assert failed.status_code == 502
    assert rows("escalations")[0]["status"] == "proposed"
    retried = http.post(f"{base}/approve", headers=as_user())
    assert retried.json()["issue_identifier"] == "ENG-1"
    actions = [r["action"] for r in rows("audit_log")]
    assert "escalation.approve_failed" in actions


def test_approve_reclaims_an_escalation_stuck_in_creating(
    http: TestClient,
    linear: FakeLinear,
    room: str,
    as_user: Headers,
    rows,
    sync_engine: Engine,
) -> None:
    connect(http, as_user())
    id = propose(http, room).json()["id"]
    stuck_creating(sync_engine, id, timedelta(minutes=10))

    response = http.post(f"/escalations/{id}/approve", headers=as_user())

    assert response.status_code == 200
    assert response.json()["status"] == "created"
    assert response.json()["issue_identifier"] == "ENG-1"
    assert len(linear.issues) == 1
    assert rows("escalations")[0]["status"] == "created"


def test_a_recently_claimed_escalation_is_still_in_progress(
    http: TestClient,
    linear: FakeLinear,
    room: str,
    as_user: Headers,
    rows,
    sync_engine: Engine,
) -> None:
    connect(http, as_user())
    id = propose(http, room).json()["id"]
    stuck_creating(sync_engine, id, timedelta(seconds=10))

    response = http.post(f"/escalations/{id}/approve", headers=as_user())

    assert response.status_code == 409
    assert linear.issues == []
    assert rows("escalations")[0]["status"] == "creating"


def test_approving_a_stuck_escalation_twice_creates_one_issue(
    http: TestClient,
    linear: FakeLinear,
    room: str,
    as_user: Headers,
    sync_engine: Engine,
) -> None:
    connect(http, as_user())
    id = propose(http, room).json()["id"]
    stuck_creating(sync_engine, id, timedelta(minutes=10))
    url = f"/escalations/{id}/approve"

    first = http.post(url, headers=as_user())
    second = http.post(url, headers=as_user())

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["status"] == "created"
    assert len(linear.issues) == 1


def test_approve_after_disconnect_is_a_409_and_stays_proposed(
    http: TestClient, linear: FakeLinear, room: str, as_user: Headers, rows
) -> None:
    connect(http, as_user())
    base = f"/escalations/{propose(http, room).json()['id']}"
    http.delete("/integrations/linear", headers=as_user())

    response = http.post(f"{base}/approve", headers=as_user())

    assert response.status_code == 409
    assert rows("escalations")[0]["status"] == "proposed"
    assert linear.issues == []


def test_an_expired_access_token_is_refreshed_and_the_new_pair_stored(
    http: TestClient, linear: FakeLinear, room: str, as_user: Headers, rows
) -> None:
    linear.expires_in = 3600
    connect(http, as_user())
    base = f"/escalations/{propose(http, room).json()['id']}"
    set_clock(NOW + 3600)

    response = http.post(f"{base}/approve", headers=as_user())

    assert response.status_code == 200
    assert linear.forms[-1]["grant_type"] == "refresh_token"
    assert linear.forms[-1]["refresh_token"] == "refresh-1"
    assert linear.authorizations[-1] == "Bearer access-2"
    [row] = rows("linear_connections")
    assert row["expires_at"] == int(NOW) + 3600 + 3600
    set_clock(NOW + 3600 + 3600)
    second = propose(http, room).json()["id"]
    http.post(f"/escalations/{second}/approve", headers=as_user())
    assert linear.forms[-1]["refresh_token"] == "refresh-2"


def test_a_connection_that_cannot_refresh_asks_for_a_reconnect(
    http: TestClient, linear: FakeLinear, room: str, as_user: Headers, rows
) -> None:
    linear.expires_in = 3600
    connect(http, as_user())
    base = f"/escalations/{propose(http, room).json()['id']}"
    set_clock(NOW + 7200)
    linear.token_status = 400

    response = http.post(f"{base}/approve", headers=as_user())

    assert response.status_code == 409
    assert "reconnect" in response.json()["detail"]
    assert rows("escalations")[0]["status"] == "proposed"
