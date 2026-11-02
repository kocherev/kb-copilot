"""Walk the quickstart flow against a running Compose stack.

Start the stack with the LiveKit profile, then run:

    uv run python scripts/smoke.py

API_PORT and WEB_PORT pick the host ports, the same variables Compose reads.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from uuid import uuid4


def request(
    method: str,
    url: str,
    body: object | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, str, list[str]]:
    data = None if body is None else json.dumps(body).encode()
    sent = dict(headers or {})
    if body is not None:
        sent["content-type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=sent)
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            cookies = response.headers.get_all("set-cookie") or []
            return response.status, response.read().decode(), cookies
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(), []


def expect(step: str, status: int, text: str, want: int) -> None:
    if status != want:
        sys.exit(f"FAIL {step}: HTTP {status}, want {want}: {text[:500]}")
    print(f"ok   {step}")


def cookie_header(set_cookies: list[str]) -> str:
    return "; ".join(cookie.split(";", 1)[0] for cookie in set_cookies)


def main() -> int:
    api = f"http://localhost:{os.environ.get('API_PORT', '8000')}"
    web = f"http://localhost:{os.environ.get('WEB_PORT', '3000')}"
    suffix = uuid4().hex[:8]
    name = f"Smoke {suffix}"

    status, text, set_cookies = request(
        "POST",
        f"{web}/api/auth/sign-up/email",
        {
            "name": "Smoke",
            "email": f"smoke-{suffix}@example.com",
            "password": f"smoke-{uuid4().hex}",
        },
        {"origin": web},
    )
    expect("sign up", status, text, 200)
    session = {"cookie": cookie_header(set_cookies)}

    status, text, _ = request("GET", f"{web}/api/auth/token", headers=session)
    expect("get JWT", status, text, 200)
    auth = {"authorization": f"Bearer {json.loads(text)['token']}"}

    status, text, _ = request("GET", f"{api}/me", headers=auth)
    expect("API accepts the JWT", status, text, 200)
    if not json.loads(text)["org_id"]:
        sys.exit("FAIL API accepts the JWT: no active organization")

    status, text, _ = request(
        "PUT", f"{api}/products/{uuid4()}", {"name": "x"}, {"origin": web}
    )
    expect("anonymous PUT is refused", status, text, 401)

    status, text, _ = request(
        "POST",
        f"{api}/products",
        {
            "name": name,
            "description": "Smoke test product.",
            "tone": "calm and brief",
            "refusal_rules": "Do not invent a refund policy.",
        },
        auth,
    )
    expect("create product", status, text, 201)
    product_id = json.loads(text)["id"]

    status, text, _ = request(
        "POST",
        f"{api}/products/{product_id}/documents",
        {"directory": "demo/docs"},
        auth,
    )
    expect("index demo/docs", status, text, 201)
    job = json.loads(text)
    if job["status"] != "indexed":
        sys.exit(f"FAIL index demo/docs: status {job['status']}: {job.get('error')}")

    for path in (f"/products/{product_id}", f"/products/{product_id}/session"):
        status, text, _ = request("GET", f"{web}{path}", headers=session)
        expect(f"web {path}", status, text, 200)
        if name not in text:
            sys.exit(f"FAIL web {path}: product name missing from the page")

    status, text, _ = request(
        "POST", f"{api}/sessions", {"product_id": product_id}, auth
    )
    expect("start session", status, text, 201)
    grant = json.loads(text)
    if not all(grant.get(key) for key in ("url", "token", "room")):
        sys.exit(f"FAIL start session: incomplete grant {sorted(grant)}")

    print("smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
