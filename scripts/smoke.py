"""Walk the quickstart flow against a running Compose stack.

Start the stack with the LiveKit profile, then run:

    uv run python scripts/smoke.py

API_PORT and WEB_PORT pick the host ports, the same variables Compose reads.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

DEMO_DOCS = Path(__file__).resolve().parents[1] / "demo" / "docs"
UPLOAD_BATCH = 20  # the API takes at most 20 files per upload
INDEX_TIMEOUT_SECONDS = 300


def request(
    method: str,
    url: str,
    body: object | tuple[bytes, str] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, str, list[str]]:
    sent = dict(headers or {})
    if isinstance(body, tuple):
        data, sent["content-type"] = body
    elif body is not None:
        data = json.dumps(body).encode()
        sent["content-type"] = "application/json"
    else:
        data = None
    req = urllib.request.Request(url, data=data, method=method, headers=sent)
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            cookies = response.headers.get_all("set-cookie") or []
            return response.status, response.read().decode(), cookies
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(), []


def upload_files(paths: list[Path]) -> tuple[bytes, str]:
    boundary = uuid4().hex
    body = (
        b"".join(
            f'--{boundary}\r\nContent-Disposition: form-data; name="files"; '
            f'filename="{path.name}"\r\n\r\n'.encode()
            + path.read_bytes()
            + b"\r\n"
            for path in paths
        )
        + f"--{boundary}--\r\n".encode()
    )
    return body, f"multipart/form-data; boundary={boundary}"


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

    documents_url = f"{api}/products/{product_id}/documents"
    paths = [
        path
        for path in sorted(DEMO_DOCS.rglob("*"))
        if path.suffix in {".md", ".html", ".pdf"}
    ]
    status, text, _ = request(
        "POST", documents_url, upload_files(paths[:1]), {"origin": web}
    )
    expect("anonymous upload is refused", status, text, 401)
    for start in range(0, len(paths), UPLOAD_BATCH):
        status, text, _ = request(
            "POST",
            documents_url,
            upload_files(paths[start : start + UPLOAD_BATCH]),
            auth,
        )
        expect(f"upload demo/docs from file {start + 1}", status, text, 202)

    deadline = time.monotonic() + INDEX_TIMEOUT_SECONDS
    while True:
        status, text, _ = request("GET", documents_url, headers=auth)
        expect("list documents", status, text, 200)
        documents = json.loads(text)
        if all(doc["status"] not in {"queued", "indexing"} for doc in documents):
            break
        if time.monotonic() > deadline:
            sys.exit("FAIL index demo/docs: still indexing after the timeout")
        time.sleep(2)
    broken = [(d["title"], d["error"]) for d in documents if d["status"] != "indexed"]
    if broken or len(documents) != len(paths):
        sys.exit(
            f"FAIL index demo/docs: {len(documents)}/{len(paths)} listed, {broken}"
        )
    print(f"ok   indexed {len(documents)} documents")

    removed = documents[0]
    status, text, _ = request(
        "DELETE", f"{documents_url}/{removed['id']}", headers=auth
    )
    expect("delete a document", status, text, 204)
    status, text, _ = request("GET", documents_url, headers=auth)
    expect("list documents after delete", status, text, 200)
    if removed["id"] in {doc["id"] for doc in json.loads(text)}:
        sys.exit("FAIL delete a document: it is still listed")

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
