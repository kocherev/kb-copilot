import json
import os
import threading
import time
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import jwt
import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from jwt.algorithms import OKPAlgorithm
from kb_api.auth import AUDIENCE
from kb_api.settings import load_settings
from sqlalchemy import Engine, create_engine, text

API_ROOT = Path(__file__).resolve().parents[1]
ISSUER = "http://web.test"
KID = "test-key"

Signer = Callable[..., str]


@pytest.fixture(autouse=True)
def fresh_settings():
    load_settings.cache_clear()
    yield
    load_settings.cache_clear()


@pytest.fixture(scope="session")
def signing_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


@pytest.fixture(scope="session")
def jwks_url(signing_key: Ed25519PrivateKey) -> Iterator[str]:
    public = json.loads(OKPAlgorithm.to_jwk(signing_key.public_key()))
    body = json.dumps({"keys": [{**public, "kid": KID, "alg": "EdDSA"}]}).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/api/auth/jwks"
    server.shutdown()
    server.server_close()


@pytest.fixture
def sign(signing_key: Ed25519PrivateKey) -> Signer:
    def mint(
        user: str = "user-a",
        org: str | None = "org-a",
        key: Ed25519PrivateKey = signing_key,
        expires_in: int = 300,
    ) -> str:
        claims: dict[str, object] = {
            "sub": user,
            "iss": ISSUER,
            "aud": AUDIENCE,
            "exp": int(time.time()) + expires_in,
        }
        if org is not None:
            claims["org_id"] = org
        return jwt.encode(claims, key, algorithm="EdDSA", headers={"kid": KID})

    return mint


@pytest.fixture
def database_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """A migrated, empty database: Postgres when KB_TEST_DATABASE_URL is set."""
    url = os.environ.get(
        "KB_TEST_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'api.db'}"
    )
    monkeypatch.setenv("DATABASE_URL", url)
    load_settings.cache_clear()
    config = Config(str(API_ROOT / "alembic.ini"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    yield url
    load_settings.cache_clear()


@pytest.fixture
def api_env(database_url: str, jwks_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_JWKS_URL", jwks_url)
    monkeypatch.setenv("AUTH_ISSUER", ISSUER)
    load_settings.cache_clear()


@pytest.fixture
def http(api_env: None) -> Iterator[TestClient]:
    from kb_api.main import app

    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def as_user(sign: Signer) -> Callable[..., dict[str, str]]:
    def headers(user: str = "user-a", org: str = "org-a") -> dict[str, str]:
        return {"authorization": f"Bearer {sign(user=user, org=org)}"}

    return headers


@pytest.fixture
def sync_engine(database_url: str) -> Iterator[Engine]:
    """A plain engine on the database the API writes to, for assertions."""
    sync_url = database_url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg")
    engine = create_engine(sync_url)
    yield engine
    engine.dispose()


@pytest.fixture
def rows(sync_engine: Engine) -> Callable[[str], list[dict[str, object]]]:
    def read(table: str) -> list[dict[str, object]]:
        with sync_engine.connect() as connection:
            result = connection.execute(text(f"SELECT * FROM {table}"))
            return [dict(row._mapping) for row in result]

    return read
