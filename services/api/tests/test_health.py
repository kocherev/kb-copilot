from fastapi.testclient import TestClient
from kb_api.main import app
from kb_api.settings import load_settings


def test_health_returns_ok() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_settings_read_environment(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://kb:replace-me@db:5432/kb")
    monkeypatch.setenv("QDRANT_URL", "http://qdrant:6333")
    monkeypatch.setenv("KB_DATA_ROOT", "/app")

    settings = load_settings()

    assert settings.database_url == "postgresql://kb:replace-me@db:5432/kb"
    assert settings.qdrant_url == "http://qdrant:6333"
    assert settings.data_root == "/app"
