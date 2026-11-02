import json
import logging
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from kb_api.main import app
from kb_api.products import MemoryProductStore, get_product_store
from kb_api.sessions import (
    AGENT_NAME,
    AgentDispatch,
    Dispatcher,
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


class RecordingDispatcher:
    def __init__(self) -> None:
        self.requests: list[AgentDispatch] = []

    async def create_dispatch(self, request: AgentDispatch) -> None:
        self.requests.append(request)


class FailingDispatcher:
    async def create_dispatch(self, request: AgentDispatch) -> None:
        raise RuntimeError(request.room)


def _override(store: MemoryProductStore, dispatcher: Dispatcher) -> TestClient:
    app.dependency_overrides[get_product_store] = lambda: store
    app.dependency_overrides[get_dispatcher] = lambda: dispatcher
    return TestClient(app)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LIVEKIT_URL", "ws://localhost:7880")
    monkeypatch.setenv("LIVEKIT_API_KEY", "test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "test-secret-placeholder-32bytes!")
    store = MemoryProductStore()
    dispatcher = RecordingDispatcher()
    http = _override(store, dispatcher)
    yield http, dispatcher
    app.dependency_overrides.clear()


def test_settings_read_livekit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "test-secret-placeholder-32bytes!")
    monkeypatch.delenv("QDRANT_API_KEY", raising=False)

    settings = load_settings()

    assert settings.livekit_url == "wss://example.livekit.cloud"
    assert settings.livekit_api_key == "test-key"
    assert settings.livekit_api_secret == "test-secret-placeholder-32bytes!"
    assert settings.qdrant_api_key == ""


def test_session_token_carries_the_room_and_dispatch_metadata(
    client: tuple[TestClient, RecordingDispatcher],
) -> None:
    http, dispatcher = client
    created = http.post("/products", json=VALID)
    assert created.status_code == 201
    product_id = created.json()["id"]
    UUID(product_id)

    started = http.post("/sessions", json={"product_id": product_id})

    assert started.status_code == 201
    body = started.json()
    assert body["url"] == "ws://localhost:7880"
    assert body["room"].startswith("kb-")
    claims = TokenVerifier("test-key", "test-secret-placeholder-32bytes!").verify(
        body["token"]
    )
    assert claims.identity == "user"
    assert claims.video is not None
    assert claims.video.room_join is True
    assert claims.video.room == body["room"]
    assert claims.video.can_publish is True
    assert claims.video.can_subscribe is True
    assert len(dispatcher.requests) == 1
    dispatch = dispatcher.requests[0]
    assert dispatch.agent_name == AGENT_NAME == "kb-support"
    assert dispatch.room == body["room"]
    assert json.loads(dispatch.metadata) == {"product_id": product_id}


def test_missing_product_does_not_dispatch(
    client: tuple[TestClient, RecordingDispatcher],
) -> None:
    http, dispatcher = client

    missing = http.post(
        "/sessions",
        json={"product_id": "00000000-0000-0000-0000-000000000000"},
    )

    assert missing.status_code == 404
    assert missing.json()["detail"] == "product not found"
    assert dispatcher.requests == []
    rejected = http.post("/sessions", json={"product_id": "demo"})
    assert rejected.status_code == 422
    assert dispatcher.requests == []


def test_missing_livekit_config_does_not_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LIVEKIT_URL", raising=False)
    monkeypatch.delenv("LIVEKIT_API_KEY", raising=False)
    monkeypatch.delenv("LIVEKIT_API_SECRET", raising=False)
    store = MemoryProductStore()
    dispatcher = RecordingDispatcher()
    http = _override(store, dispatcher)
    created = http.post("/products", json=VALID)
    assert created.status_code == 201

    started = http.post("/sessions", json={"product_id": created.json()["id"]})

    assert started.status_code == 503
    assert started.json()["detail"] == "LiveKit is not configured"
    assert dispatcher.requests == []
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("key", "secret"),
    [("replace-me", "replace-me"), ("test-key", ""), ("", "test-secret")],
)
def test_placeholder_livekit_config_is_not_configured(
    monkeypatch: pytest.MonkeyPatch, key: str, secret: str
) -> None:
    monkeypatch.setenv("LIVEKIT_URL", "ws://localhost:7880")
    monkeypatch.setenv("LIVEKIT_API_KEY", key)
    monkeypatch.setenv("LIVEKIT_API_SECRET", secret)
    store = MemoryProductStore()
    dispatcher = RecordingDispatcher()
    http = _override(store, dispatcher)
    created = http.post("/products", json=VALID)

    started = http.post("/sessions", json={"product_id": created.json()["id"]})

    assert started.status_code == 503
    assert started.json()["detail"] == "LiveKit is not configured"
    assert dispatcher.requests == []
    app.dependency_overrides.clear()


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
    monkeypatch: pytest.MonkeyPatch, livekit_api: tuple[str, list[str]]
) -> None:
    api_url, paths = livekit_api
    monkeypatch.setenv("LIVEKIT_URL", "ws://browser-only.invalid:7880")
    monkeypatch.setenv("LIVEKIT_API_URL", api_url)
    monkeypatch.setenv("LIVEKIT_API_KEY", "test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "test-secret-placeholder-32bytes!")
    store = MemoryProductStore()
    app.dependency_overrides[get_product_store] = lambda: store
    http = TestClient(app)
    created = http.post("/products", json=VALID)

    started = http.post("/sessions", json={"product_id": created.json()["id"]})

    assert started.status_code == 201
    assert started.json()["url"] == "ws://browser-only.invalid:7880"
    assert paths == ["/twirp/livekit.AgentDispatchService/CreateDispatch"]
    app.dependency_overrides.clear()


def test_dispatch_failure_does_not_return_a_token(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("LIVEKIT_URL", "ws://localhost:7880")
    monkeypatch.setenv("LIVEKIT_API_KEY", "test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "test-secret-placeholder-32bytes!")
    store = MemoryProductStore()
    http = _override(store, FailingDispatcher())
    created = http.post("/products", json=VALID)
    assert created.status_code == 201

    started = http.post("/sessions", json={"product_id": created.json()["id"]})

    assert started.status_code == 502
    assert started.json()["detail"] == "Could not dispatch the agent"
    assert "token" not in started.json()
    [record] = [r for r in caplog.records if r.name == "kb_api.sessions"]
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None
    assert isinstance(record.exc_info[1], RuntimeError)
    app.dependency_overrides.clear()
