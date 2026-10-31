import os

import pytest
from fastapi.testclient import TestClient
from kb_api.main import app

pytestmark = pytest.mark.skipif(
    os.environ.get("KB_LIVE_STORES") != "1",
    reason="set KB_LIVE_STORES=1 to hit Postgres and Qdrant",
)

VALID = {
    "name": "Live Acme",
    "description": "Live Acme helps customers reset passwords.",
    "tone": "calm and brief",
    "refusal_rules": "Do not invent a refund policy.",
}


def test_live_product_config_round_trip_and_upload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.dependency_overrides.clear()
    monkeypatch.setenv(
        "DATABASE_URL",
        os.environ.get(
            "DATABASE_URL",
            "postgresql://kb:replace-me@localhost:5432/kb",
        ),
    )
    monkeypatch.setenv(
        "QDRANT_URL", os.environ.get("QDRANT_URL", "http://localhost:6333")
    )
    client = TestClient(app)

    created = client.post("/products", json=VALID)
    assert created.status_code == 201
    product_id = created.json()["id"]
    assert client.get(f"/products/{product_id}").json()["name"] == "Live Acme"

    updated = client.put(
        f"/products/{product_id}",
        json={**VALID, "tone": "warm and direct"},
    )
    assert updated.status_code == 200
    assert client.get(f"/products/{product_id}").json()["tone"] == "warm and direct"

    uploaded = client.post(
        f"/products/{product_id}/documents",
        files=[
            (
                "files",
                (
                    "notes.md",
                    b"# Notes\n\nPassword reset links expire after 30 minutes.\n",
                    "text/markdown",
                ),
            )
        ],
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["status"] == "indexed"
    assert uploaded.json()["product_id"] == product_id
