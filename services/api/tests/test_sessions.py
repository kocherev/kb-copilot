import asyncio
import json
import logging
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import jwt
import pytest
from fastapi.testclient import TestClient
from kb_api.sessions import (
    AGENT_NAME,
    AgentDispatch,
    Dispatcher,
    get_clock,
    get_dispatcher,
)
from kb_api.settings import load_settings
from livekit.api import TokenVerifier

VALID = {
    "name": "Acme",
    "description": "Acme helps customers reset passwords.",
    "tone": "calm and brief",
    "refusal_rules": "Do not invent a refund policy.",
}
SECRET = "test-secret-placeholder-32bytes!"


class RecordingDispatcher:
    def __init__(self) -> None:
        self.requests: list[AgentDispatch] = []

    async def create_dispatch(self, request: AgentDispatch) -> None:
        self.requests.append(request)


class FailingDispatcher:
    async def create_dispatch(self, request: AgentDispatch) -> None:
        raise RuntimeError(request.room)


def use_dispatcher(dispatcher: Dispatcher) -> None:
    from kb_api.main import app

    app.dependency_overrides[get_dispatcher] = lambda: dispatcher


def freeze_clock(now: float) -> None:
    from kb_api.main import app

    app.dependency_overrides[get_clock] = lambda: lambda: now


@pytest.fixture
def livekit_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIVEKIT_URL", "ws://localhost:7880")
    monkeypatch.setenv("LIVEKIT_API_KEY", "test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", SECRET)
    load_settings.cache_clear()


@pytest.fixture
def dispatcher(livekit_env: None, http: TestClient) -> RecordingDispatcher:
    recording = RecordingDispatcher()
    use_dispatcher(recording)
    return recording


def create_product(http: TestClient, headers: dict[str, str]) -> str:
    created = http.post("/products", json=VALID, headers=headers)
    assert created.status_code == 201
    return created.json()["id"]


def test_settings_read_livekit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", SECRET)
    monkeypatch.delenv("QDRANT_API_KEY", raising=False)

    settings = load_settings()

    assert settings.livekit_url == "wss://example.livekit.cloud"
    assert settings.livekit_api_key == "test-key"
    assert settings.livekit_api_secret == SECRET
    assert settings.qdrant_api_key == ""
    assert settings.livekit_token_ttl_seconds == 900
    assert settings.session_rate_limit == 10


def test_session_token_carries_the_user_room_and_dispatch_metadata(
    http: TestClient, dispatcher: RecordingDispatcher, as_user, rows
) -> None:
    headers = as_user(user="user-a", org="org-a")
    product_id = create_product(http, headers)

    started = http.post("/sessions", json={"product_id": product_id}, headers=headers)

    assert started.status_code == 201
    body = started.json()
    assert body["url"] == "ws://localhost:7880"
    assert body["room"].startswith("kb-")
    claims = TokenVerifier("test-key", SECRET).verify(body["token"])
    assert claims.identity == "user:user-a"
    assert claims.video is not None
    assert claims.video.room_join is True
    assert claims.video.room == body["room"]
    assert claims.video.can_publish is True
    assert claims.video.can_subscribe is True
    [dispatch] = dispatcher.requests
    assert dispatch.agent_name == AGENT_NAME == "kb-support"
    assert dispatch.room == body["room"]
    assert json.loads(dispatch.metadata) == {"product_id": product_id}

    listed = http.get("/sessions", headers=headers).json()
    assert [(item["room"], item["product_id"], item["user_id"]) for item in listed] == [
        (body["room"], product_id, "user-a")
    ]
    assert http.get("/sessions", headers=as_user(org="org-b")).json() == []
    actions = [row["action"] for row in rows("audit_log")]
    assert actions.count("session.create") == 1


def test_token_ttl_comes_from_settings(
    http: TestClient,
    dispatcher: RecordingDispatcher,
    as_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = as_user()
    product_id = create_product(http, headers)

    def ttl() -> int:
        token = http.post(
            "/sessions", json={"product_id": product_id}, headers=headers
        ).json()["token"]
        claims = jwt.decode(token, SECRET, algorithms=["HS256"])
        return claims["exp"] - claims["nbf"]

    assert ttl() == 900
    monkeypatch.setenv("LIVEKIT_TOKEN_TTL_SECONDS", "120")
    load_settings.cache_clear()
    assert ttl() == 120


def test_session_starts_are_rate_limited_per_org(
    http: TestClient,
    dispatcher: RecordingDispatcher,
    as_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SESSION_RATE_LIMIT", "2")
    load_settings.cache_clear()
    freeze_clock(60 * 1_000_000 + 15)
    org_a = as_user(org="org-a")
    org_b = as_user(user="user-b", org="org-b")
    product_a = create_product(http, org_a)
    product_b = create_product(http, org_b)

    statuses = [
        http.post("/sessions", json={"product_id": product_a}, headers=org_a)
        for _ in range(3)
    ]

    assert [response.status_code for response in statuses] == [201, 201, 429]
    limited = statuses[-1]
    assert limited.json() == {"detail": "too many sessions, try again shortly"}
    assert limited.headers["retry-after"] == "45"
    assert len(dispatcher.requests) == 2
    other = http.post("/sessions", json={"product_id": product_b}, headers=org_b)
    assert other.status_code == 201
    freeze_clock(60 * 1_000_001)
    next_minute = http.post("/sessions", json={"product_id": product_a}, headers=org_a)
    assert next_minute.status_code == 201


def test_missing_or_foreign_product_does_not_dispatch(
    http: TestClient, dispatcher: RecordingDispatcher, as_user
) -> None:
    foreign = create_product(http, as_user(org="org-b"))
    headers = as_user(org="org-a")

    missing = http.post(
        "/sessions",
        json={"product_id": "00000000-0000-0000-0000-000000000000"},
        headers=headers,
    )
    other_org = http.post("/sessions", json={"product_id": foreign}, headers=headers)
    rejected = http.post("/sessions", json={"product_id": "demo"}, headers=headers)

    assert missing.status_code == 404
    assert missing.json()["detail"] == "product not found"
    assert other_org.status_code == 404
    assert rejected.status_code == 422
    assert dispatcher.requests == []


@pytest.mark.parametrize(
    ("url", "key", "secret"),
    [
        ("", "", ""),
        ("ws://localhost:7880", "replace-me", "replace-me"),
        ("ws://localhost:7880", "test-key", ""),
        ("ws://localhost:7880", "", "test-secret"),
    ],
)
def test_missing_livekit_config_does_not_dispatch(
    http: TestClient,
    as_user,
    monkeypatch: pytest.MonkeyPatch,
    url: str,
    key: str,
    secret: str,
) -> None:
    monkeypatch.setenv("LIVEKIT_URL", url)
    monkeypatch.setenv("LIVEKIT_API_KEY", key)
    monkeypatch.setenv("LIVEKIT_API_SECRET", secret)
    load_settings.cache_clear()
    recording = RecordingDispatcher()
    use_dispatcher(recording)
    headers = as_user()
    product_id = create_product(http, headers)

    started = http.post("/sessions", json={"product_id": product_id}, headers=headers)

    assert started.status_code == 503
    assert started.json()["detail"] == "LiveKit is not configured"
    assert recording.requests == []


@pytest.fixture
def livekit_api() -> Iterator[tuple[str, list[str]]]:
    paths: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.rfile.read(int(self.headers["content-length"]))
            paths.append(self.path)
            self.send_response(200)
            self.send_header("content-length", "0")
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", paths
    server.shutdown()
    server.server_close()


def test_dispatch_uses_the_server_side_livekit_url(
    http: TestClient,
    as_user,
    monkeypatch: pytest.MonkeyPatch,
    livekit_api: tuple[str, list[str]],
) -> None:
    api_url, paths = livekit_api
    monkeypatch.setenv("LIVEKIT_URL", "ws://browser-only.invalid:7880")
    monkeypatch.setenv("LIVEKIT_API_URL", api_url)
    monkeypatch.setenv("LIVEKIT_API_KEY", "test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", SECRET)
    load_settings.cache_clear()
    headers = as_user()
    product_id = create_product(http, headers)

    started = http.post("/sessions", json={"product_id": product_id}, headers=headers)

    assert started.status_code == 201
    assert started.json()["url"] == "ws://browser-only.invalid:7880"
    assert paths == ["/twirp/livekit.AgentDispatchService/CreateDispatch"]


def test_dispatch_failure_does_not_return_a_token(
    http: TestClient,
    livekit_env: None,
    as_user,
    caplog: pytest.LogCaptureFixture,
) -> None:
    use_dispatcher(FailingDispatcher())
    headers = as_user()
    product_id = create_product(http, headers)

    started = http.post("/sessions", json={"product_id": product_id}, headers=headers)

    assert started.status_code == 502
    assert started.json()["detail"] == "Could not dispatch the agent"
    assert "token" not in started.json()
    [record] = [r for r in caplog.records if r.name == "kb_api.sessions"]
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None
    assert isinstance(record.exc_info[1], RuntimeError)
    assert http.get("/sessions", headers=headers).json() == []


def test_failed_dispatch_gives_the_rate_limit_slot_back(
    http: TestClient,
    livekit_env: None,
    as_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SESSION_RATE_LIMIT", "1")
    load_settings.cache_clear()
    freeze_clock(60 * 1_000_000)
    headers = as_user()
    product_id = create_product(http, headers)
    use_dispatcher(FailingDispatcher())

    failed = [
        http.post("/sessions", json={"product_id": product_id}, headers=headers)
        for _ in range(3)
    ]
    use_dispatcher(RecordingDispatcher())
    started = http.post("/sessions", json={"product_id": product_id}, headers=headers)

    assert [response.status_code for response in failed] == [502, 502, 502]
    assert started.status_code == 201


def test_concurrent_starts_are_each_counted_once(database_url: str) -> None:
    from fastapi import HTTPException
    from kb_api.sessions import take_session_slot
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    async def race() -> list[int]:
        engine = create_async_engine(load_settings().async_database_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)

        async def start() -> int:
            try:
                await take_session_slot(sessions, "org-a", 5, 60 * 1_000_000)
            except HTTPException as exc:
                return exc.status_code
            return 201

        statuses = await asyncio.gather(*(start() for _ in range(8)))
        await engine.dispose()
        return sorted(statuses)

    assert asyncio.run(race()) == [201] * 5 + [429] * 3


def start_session(http: TestClient, headers: dict[str, str]) -> str:
    product_id = create_product(http, headers)
    return http.post(
        "/sessions", json={"product_id": product_id}, headers=headers
    ).json()["room"]


def test_desktop_token_is_rpc_only_and_short_lived(
    http: TestClient, dispatcher: RecordingDispatcher, as_user, rows
) -> None:
    headers = as_user(user="user-a", org="org-a")
    room = start_session(http, headers)

    granted = http.post(f"/sessions/{room}/desktop-token", headers=headers)

    assert granted.status_code == 200
    body = granted.json()
    assert body["url"] == "ws://localhost:7880"
    claims = TokenVerifier("test-key", SECRET).verify(body["token"])
    assert claims.identity == "desktop:user-a"
    assert claims.video is not None
    assert claims.video.room_join is True
    assert claims.video.room == room
    assert claims.video.can_publish is False
    assert claims.video.can_publish_data is True
    assert claims.video.can_subscribe is False
    decoded = jwt.decode(body["token"], SECRET, algorithms=["HS256"])
    assert decoded["exp"] - decoded["nbf"] == 600
    assert [row["action"] for row in rows("audit_log")].count(
        "session.desktop_token"
    ) == 1


def test_desktop_token_is_only_for_the_session_owner(
    http: TestClient, dispatcher: RecordingDispatcher, as_user
) -> None:
    room = start_session(http, as_user(user="user-a", org="org-a"))
    others = [
        as_user(user="user-b", org="org-a"),
        as_user(user="user-a", org="org-b"),
    ]

    stranger = [http.post(f"/sessions/{room}/desktop-token", headers=h) for h in others]
    unknown = http.post(
        "/sessions/kb-nothing/desktop-token", headers=as_user(user="user-a")
    )
    anonymous = http.post(f"/sessions/{room}/desktop-token")

    assert [response.status_code for response in stranger] == [404, 404]
    assert unknown.status_code == 404
    assert anonymous.status_code == 401


def test_desktop_token_needs_a_signed_in_user(
    http: TestClient, dispatcher: RecordingDispatcher, as_user
) -> None:
    owner = as_user(user="user-a", org="org-a")
    room = start_session(http, owner)
    secret = http.post("/api-keys", json={"name": "CI"}, headers=owner).json()["secret"]

    machine = http.post(
        f"/sessions/{room}/desktop-token",
        headers={"authorization": f"Bearer {secret}"},
    )

    assert machine.status_code == 403


def test_desktop_token_without_livekit_config_is_unavailable(
    http: TestClient,
    dispatcher: RecordingDispatcher,
    as_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = as_user()
    room = start_session(http, headers)
    monkeypatch.setenv("LIVEKIT_API_SECRET", "replace-me")
    load_settings.cache_clear()

    unavailable = http.post(f"/sessions/{room}/desktop-token", headers=headers)

    assert unavailable.status_code == 503
    assert "token" not in unavailable.json()
