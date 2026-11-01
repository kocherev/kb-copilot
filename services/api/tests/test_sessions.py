import json
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


def test_dispatch_failure_does_not_return_a_token(
    monkeypatch: pytest.MonkeyPatch,
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
    app.dependency_overrides.clear()
