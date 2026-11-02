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


def request(method: str, url: str, body: object | None = None) -> tuple[int, str]:
    data = None if body is None else json.dumps(body).encode()
    headers = {} if body is None else {"content-type": "application/json"}
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def expect(step: str, status: int, text: str, want: int) -> None:
    if status != want:
        sys.exit(f"FAIL {step}: HTTP {status}, want {want}: {text[:500]}")
    print(f"ok   {step}")


def main() -> int:
    api = f"http://localhost:{os.environ.get('API_PORT', '8000')}"
    web = f"http://localhost:{os.environ.get('WEB_PORT', '3000')}"
    name = f"Smoke {uuid4().hex[:8]}"

    status, text = request(
        "POST",
        f"{api}/products",
        {
            "name": name,
            "description": "Smoke test product.",
            "tone": "calm and brief",
            "refusal_rules": "Do not invent a refund policy.",
        },
    )
    expect("create product", status, text, 201)
    product_id = json.loads(text)["id"]

    status, text = request(
        "POST", f"{api}/products/{product_id}/documents", {"directory": "demo/docs"}
    )
    expect("index demo/docs", status, text, 201)
    job = json.loads(text)
    if job["status"] != "indexed":
        sys.exit(f"FAIL index demo/docs: status {job['status']}: {job.get('error')}")

    for path in (f"/products/{product_id}", f"/products/{product_id}/session"):
        status, text = request("GET", f"{web}{path}")
        expect(f"web {path}", status, text, 200)
        if name not in text:
            sys.exit(f"FAIL web {path}: product name missing from the page")

    status, text = request("POST", f"{api}/sessions", {"product_id": product_id})
    expect("start session", status, text, 201)
    grant = json.loads(text)
    if not all(grant.get(key) for key in ("url", "token", "room")):
        sys.exit(f"FAIL start session: incomplete grant {sorted(grant)}")

    print("smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
