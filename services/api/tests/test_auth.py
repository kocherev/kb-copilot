import socket
import threading
import time
from collections.abc import Iterator

import httpx
import jwt
import pytest
import uvicorn
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

VALID = {
    "name": "Acme",
    "description": "Acme helps customers reset passwords.",
    "tone": "calm and brief",
    "refusal_rules": "Do not invent a refund policy.",
}


def bearer(token: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token}"}


def test_me_returns_the_user_and_active_org(http: TestClient, as_user) -> None:
    response = http.get("/me", headers=as_user(user="user-a", org="org-a"))

    assert response.status_code == 200
    assert response.json() == {"user_id": "user-a", "org_id": "org-a"}


def test_bad_tokens_are_rejected(http: TestClient, sign) -> None:
    stranger = Ed25519PrivateKey.generate()

    wrong_key = http.get("/products", headers=bearer(sign(signer=stranger)))
    expired = http.get("/products", headers=bearer(sign(expires_in=-60)))
    garbage = http.get("/products", headers=bearer("not-a-jwt"))
    no_org = http.get("/products", headers=bearer(sign(org=None)))

    assert wrong_key.status_code == 401
    assert wrong_key.json() == {"detail": "invalid token"}
    assert expired.status_code == 401
    assert garbage.status_code == 401
    assert no_org.status_code == 403
    assert no_org.json() == {"detail": "no active organization"}


def test_tokens_for_another_audience_or_issuer_are_rejected(
    http: TestClient, sign
) -> None:
    other_audience = http.get("/me", headers=bearer(sign(audience="other-api")))
    other_issuer = http.get("/me", headers=bearer(sign(issuer="http://evil.test")))
    unsigned = http.get("/me", headers=bearer(sign(unsigned=True)))

    assert other_audience.status_code == 401
    assert other_issuer.status_code == 401
    assert unsigned.status_code == 401


def test_unknown_key_ids_do_not_refetch_the_key_set_every_time(
    http: TestClient, sign, jwks_fetches: list[str]
) -> None:
    assert http.get("/me", headers=bearer(sign())).status_code == 200
    fetched = len(jwks_fetches)

    for index in range(5):
        response = http.get("/me", headers=bearer(sign(kid=f"unknown-{index}")))
        assert response.status_code == 401

    assert len(jwks_fetches) == fetched


def test_a_slow_key_set_times_out() -> None:
    from kb_api.auth import jwks_client

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    client = jwks_client(f"http://127.0.0.1:{sock.getsockname()[1]}/jwks", timeout=0.2)
    started = time.monotonic()

    with pytest.raises(jwt.PyJWKClientConnectionError):
        client.get_jwk_set()

    assert time.monotonic() - started < 2
    sock.close()


def test_api_key_acts_for_its_org_until_revoked(
    http: TestClient, as_user, rows
) -> None:
    owner = as_user(user="user-a", org="org-a")
    created = http.post("/api-keys", json={"name": "CI"}, headers=owner)
    assert created.status_code == 201
    key = created.json()
    assert key["secret"].startswith(f"kb_{key['prefix']}_")
    machine = bearer(key["secret"])

    product = http.post("/products", json=VALID, headers=machine)
    assert product.status_code == 201
    assert http.get("/products", headers=owner).json() == [
        {**product.json(), "document_count": 0, "last_session_at": None}
    ]
    assert http.get("/api-keys", headers=machine).status_code == 403
    assert http.get("/me", headers=machine).status_code == 403

    listed = http.get("/api-keys", headers=owner).json()
    assert [item["id"] for item in listed] == [key["id"]]
    assert "secret" not in listed[0]
    assert listed[0]["last_used_at"] is not None
    http.get("/products", headers=machine)
    used_again = http.get("/api-keys", headers=owner).json()[0]["last_used_at"]
    assert used_again == listed[0]["last_used_at"]
    stored = rows("api_keys")
    assert key["secret"] not in {str(value) for value in stored[0].values()}

    other = as_user(user="user-b", org="org-b")
    assert http.delete(f"/api-keys/{key['id']}", headers=other).status_code == 404
    assert http.delete(f"/api-keys/{key['id']}", headers=owner).status_code == 204
    revoked = http.get("/products", headers=machine)
    assert revoked.status_code == 401
    assert revoked.json() == {"detail": "invalid API key"}
    assert http.get("/api-keys", headers=owner).json()[0]["revoked_at"] is not None

    actions = [(row["action"], row["actor"]) for row in rows("audit_log")]
    assert ("api_key.create", "user:user-a") in actions
    assert ("product.create", f"api_key:{key['id']}") in actions
    assert ("api_key.revoke", "user:user-a") in actions


def test_forged_api_key_is_rejected(http: TestClient, as_user) -> None:
    key = http.post("/api-keys", json={"name": "CI"}, headers=as_user()).json()

    forged = http.get("/products", headers=bearer(f"kb_{key['prefix']}_guess"))
    malformed = http.get("/products", headers=bearer("kb_"))

    assert forged.status_code == 401
    assert malformed.status_code == 401


def test_internal_token_reads_any_org_product(
    http: TestClient, as_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kb_api.settings import load_settings

    product = http.post("/products", json=VALID, headers=as_user(org="org-a")).json()
    path = f"/products/{product['id']}"

    unset = http.get(path, headers={"x-internal-token": "replace-me"})
    assert unset.status_code == 503
    assert unset.json() == {"detail": "internal token is not configured"}

    monkeypatch.setenv("INTERNAL_API_TOKEN", "agent-secret")
    load_settings.cache_clear()
    assert http.get(path, headers={"x-internal-token": "nope"}).status_code == 401
    read = http.get(path, headers={"x-internal-token": "agent-secret"})
    assert read.status_code == 200
    assert read.json() == product
    write = http.put(path, json=VALID, headers={"x-internal-token": "agent-secret"})
    assert write.status_code == 401


@pytest.fixture
def live_api(api_env: None) -> Iterator[str]:
    from kb_api.main import app

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]})
    thread.start()
    while not server.started:
        time.sleep(0.01)
    yield f"http://127.0.0.1:{sock.getsockname()[1]}"
    server.should_exit = True
    thread.join()


def test_agent_reads_the_product_with_the_internal_token(
    live_api: str, as_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kb_agent.product import fetch_product
    from kb_api.settings import load_settings

    created = httpx.post(f"{live_api}/products", json=VALID, headers=as_user())
    assert created.status_code == 201
    monkeypatch.setenv("INTERNAL_API_TOKEN", "agent-secret")
    load_settings.cache_clear()

    fetched = fetch_product(live_api, created.json()["id"])

    assert fetched.name == "Acme"
    assert fetched.refusal_rules == VALID["refusal_rules"]
