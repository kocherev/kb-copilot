from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from kb_api.settings import load_settings

VALID = {
    "name": "Acme",
    "description": "Acme helps customers reset passwords.",
    "tone": "calm and brief",
    "refusal_rules": "Do not invent a refund policy.",
}
MISSING = "00000000-0000-0000-0000-000000000000"


def test_settings_read_cors_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000, http://127.0.0.1:3000")

    assert load_settings().cors_origins == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_async_database_url_uses_asyncpg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://kb:pw@db:5432/kb")

    assert load_settings().async_database_url == "postgresql+asyncpg://kb:pw@db:5432/kb"
    assert load_settings().database_url == "postgresql://kb:pw@db:5432/kb"


def test_anonymous_requests_are_rejected(http: TestClient) -> None:
    calls = [
        http.get("/products"),
        http.post("/products", json=VALID),
        http.get(f"/products/{MISSING}"),
        http.put(f"/products/{MISSING}", json=VALID),
        http.delete(f"/products/{MISSING}"),
        http.post("/sessions", json={"product_id": MISSING}),
        http.get("/sessions"),
        http.get("/api-keys"),
        http.get("/me"),
    ]

    assert [response.status_code for response in calls] == [401] * len(calls)
    assert calls[0].json() == {"detail": "not authenticated"}
    assert calls[0].headers["www-authenticate"] == "Bearer"
    assert http.get("/health").status_code == 200


def test_create_list_get_put_and_delete_product(http: TestClient, as_user) -> None:
    headers = as_user()

    created = http.post(
        "/products", json={**VALID, "tone": "  calm and brief  "}, headers=headers
    )

    assert created.status_code == 201
    body = created.json()
    UUID(body["id"])
    assert body == {
        "id": body["id"],
        **VALID,
        "agent_name": "Shawn",
        "voice": "Sulafat",
    }
    assert http.get(f"/products/{body['id']}", headers=headers).json() == body
    assert http.get("/products", headers=headers).json() == [body]

    updated = http.put(
        f"/products/{body['id']}",
        json={
            **VALID,
            "name": "Acme Care",
            "refusal_rules": "Do not share invoices.\nDo not promise a refund.",
        },
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Acme Care"
    assert "\n" in updated.json()["refusal_rules"]
    fetched = http.get(f"/products/{body['id']}", headers=headers)
    assert fetched.json()["name"] == "Acme Care"

    deleted = http.delete(f"/products/{body['id']}", headers=headers)
    assert deleted.status_code == 204
    assert http.get(f"/products/{body['id']}", headers=headers).status_code == 404
    assert http.get("/products", headers=headers).json() == []


def test_another_org_cannot_see_or_change_a_product(http: TestClient, as_user) -> None:
    created = http.post("/products", json=VALID, headers=as_user(org="org-a"))
    product_id = created.json()["id"]
    other = as_user(user="user-b", org="org-b")

    assert http.get(f"/products/{product_id}", headers=other).status_code == 404
    put = http.put(f"/products/{product_id}", json=VALID, headers=other)
    assert put.status_code == 404
    assert put.json() == {"detail": "product not found"}
    assert http.delete(f"/products/{product_id}", headers=other).status_code == 404
    assert http.get("/products", headers=other).json() == []
    teammate = as_user(user="user-c", org="org-a")
    assert http.get(f"/products/{product_id}", headers=teammate).status_code == 200


def test_invalid_product_config_is_rejected(http: TestClient, as_user) -> None:
    headers = as_user()

    def field_error(payload: dict[str, str]) -> list[object]:
        response = http.post("/products", json=payload, headers=headers)
        assert response.status_code == 422
        return [error["loc"] for error in response.json()["detail"]]

    assert field_error({**VALID, "name": "  "}) == [["body", "name"]]
    assert field_error({**VALID, "name": "A" * 121}) == [["body", "name"]]
    assert field_error({**VALID, "description": "Line one.\nLine two."}) == [
        ["body", "description"]
    ]
    assert field_error({**VALID, "tone": "warm\ndirect"}) == [["body", "tone"]]
    assert field_error({**VALID, "refusal_rules": "\n"}) == [["body", "refusal_rules"]]
    assert http.post("/products", json={**VALID, "name": "A"}, headers=headers).json()[
        "name"
    ] == ("A")
    rejected = http.get("/products/not-a-uuid", headers=headers)
    assert rejected.status_code == 422
    assert rejected.json()["detail"][0]["loc"] == ["path", "product_id"]
    assert http.get(f"/products/{MISSING}", headers=headers).status_code == 404
    assert http.put(
        f"/products/{MISSING}", json=VALID, headers=headers
    ).status_code == (404)


def test_agent_name_and_voice_are_saved_and_validated(
    http: TestClient, as_user
) -> None:
    headers = as_user()
    persona = {"agent_name": "  Mina ", "voice": "Achird"}

    created = http.post("/products", json={**VALID, **persona}, headers=headers)

    assert created.status_code == 201
    assert created.json()["agent_name"] == "Mina"
    assert created.json()["voice"] == "Achird"
    for bad in (
        {"agent_name": " "},
        {"agent_name": "A" * 41},
        {"agent_name": "Mi\nna"},
        {"voice": "Zephyr"},
        {"voice": ""},
    ):
        rejected = http.post("/products", json={**VALID, **bad}, headers=headers)
        assert rejected.status_code == 422, bad
        assert rejected.json()["detail"][0]["loc"] == ["body", *bad]


def test_openapi_documents_bodies_and_limits(http: TestClient) -> None:
    schema = http.get("/openapi.json").json()

    write = schema["components"]["schemas"]["ProductWrite"]["properties"]
    assert write["name"]["maxLength"] == 120
    assert write["description"]["maxLength"] == 2000
    assert write["tone"]["maxLength"] == 200
    assert write["refusal_rules"]["maxLength"] == 4000
    assert write["name"]["minLength"] == 1
    assert write["agent_name"]["maxLength"] == 40
    assert write["voice"]["enum"][0] == "Sulafat"
    put = schema["paths"]["/products/{product_id}"]["put"]
    assert put["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ProductWrite"
    }
    assert put["responses"]["404"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorBody"
    }
    assert {"HTTPBearer", "InternalToken"} <= set(
        schema["components"]["securitySchemes"]
    )


def test_mutations_write_audit_rows(http: TestClient, as_user, rows) -> None:
    headers = as_user(user="user-a", org="org-a")
    product_id = http.post("/products", json=VALID, headers=headers).json()["id"]
    http.put(
        f"/products/{product_id}", json={**VALID, "name": "Acme 2"}, headers=headers
    )
    http.delete(f"/products/{product_id}", headers=headers)

    audit = sorted(rows("audit_log"), key=lambda row: str(row["at"]))
    assert [row["action"] for row in audit] == [
        "product.create",
        "product.update",
        "product.delete",
    ]
    assert {row["actor"] for row in audit} == {"user:user-a"}
    assert {row["org_id"] for row in audit} == {"org-a"}
    assert {row["target"] for row in audit} == {f"product:{product_id}"}


def test_browser_origin_can_call_the_api(http: TestClient) -> None:
    allowed = http.options(
        "/products",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    local = http.options(
        "/products/x",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert local.status_code == 200
    assert local.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"

    blocked = http.get("/health", headers={"Origin": "http://evil.example"})
    assert blocked.headers.get("access-control-allow-origin") != "http://evil.example"
