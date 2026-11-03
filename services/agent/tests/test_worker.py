import asyncio
import json
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
from agent_fakes import FakeRoom
from kb_agent import worker
from kb_agent.product import (
    load_product,
    product_from_body,
    product_id_from_metadata,
    user_from_metadata,
)
from kb_agent.prompt import render_system_prompt
from kb_agent.protocol import AGENT_ERROR_TOPIC

PRODUCT_ID = "11111111-1111-4111-8111-111111111111"
PRODUCT = {
    "id": PRODUCT_ID,
    "name": "Acme",
    "description": "Acme helps customers reset passwords.",
    "tone": "calm and brief",
    "refusal_rules": "Do not invent a refund policy.",
    "agent_name": "Mina",
    "voice": "Achird",
}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == f"/products/{PRODUCT_ID}":
            body = json.dumps(PRODUCT).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, message: str, *args: object) -> None:
        return


@pytest.fixture
def api_url() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host = str(server.server_address[0])
    port = int(server.server_address[1])
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()


def test_dispatch_metadata_selects_the_product_prompt(api_url: str) -> None:
    metadata = json.dumps({"product_id": PRODUCT_ID})

    product = load_product(metadata, api_url)
    instructions = render_system_prompt(product)

    assert product_id_from_metadata(metadata) == PRODUCT_ID
    assert "You are Mina, the support agent for Acme." in instructions
    assert product.voice == "Achird"
    assert "Tone: calm and brief" in instructions
    assert "Do not invent a refund policy." in instructions
    with pytest.raises(ValueError, match="product_id is required"):
        product_id_from_metadata("{}")
    with pytest.raises(ValueError, match="JSON"):
        product_id_from_metadata("not-json")
    with pytest.raises(ValueError, match="404"):
        load_product(
            json.dumps({"product_id": "00000000-0000-0000-0000-000000000000"}),
            api_url,
        )


def test_dispatch_metadata_names_the_user_when_the_api_sends_one() -> None:
    named = json.dumps({"product_id": PRODUCT_ID, "user": "user:abc"})

    assert user_from_metadata(named) == "user:abc"
    assert user_from_metadata(json.dumps({"product_id": PRODUCT_ID})) is None
    assert user_from_metadata(json.dumps({"product_id": PRODUCT_ID, "user": 7})) is None


class _Job:
    metadata = json.dumps({"product_id": PRODUCT_ID})


class _Ctx:
    def __init__(self, room: FakeRoom) -> None:
        self.room = room
        self.job = _Job()
        self.stopped: str | None = None

    async def connect(self) -> None:
        return None

    def shutdown(self, reason: str = "") -> None:
        self.stopped = reason

    def add_shutdown_callback(self, callback: object) -> None:
        return None


class _BrokenSession:
    def on(self, event: str, callback: object = None) -> object:
        return callback or (lambda handler: handler)

    async def start(self, **kwargs: object) -> None:
        raise RuntimeError("model refused the connection")


def test_a_model_that_cannot_start_tells_the_room_why(
    api_url: str, monkeypatch: pytest.MonkeyPatch, room: FakeRoom
) -> None:
    monkeypatch.setenv("API_URL", api_url)
    voices: list[str] = []

    def broken(voice: str) -> _BrokenSession:
        voices.append(voice)
        return _BrokenSession()

    monkeypatch.setattr(worker, "build_session", broken)
    ctx = _Ctx(room)

    asyncio.run(worker.entrypoint(ctx))  # type: ignore[arg-type]

    assert voices == ["Achird"]
    [(topic, body)] = room.sent
    assert topic == AGENT_ERROR_TOPIC
    assert "could not start" in str(body["message"])
    assert "RuntimeError" in str(body["message"])
    assert ctx.stopped == "agent error"


def test_a_product_without_a_name_or_voice_for_the_agent_is_rejected() -> None:
    for key in ("agent_name", "voice"):
        body = {k: v for k, v in PRODUCT.items() if k != key}

        with pytest.raises(ValueError, match=f"{key} is required"):
            product_from_body(body)


def test_a_missing_product_also_tells_the_room(
    api_url: str, monkeypatch: pytest.MonkeyPatch, room: FakeRoom
) -> None:
    monkeypatch.setenv("API_URL", api_url)
    ctx = _Ctx(room)
    ctx.job.metadata = json.dumps({"product_id": "missing"})

    asyncio.run(worker.entrypoint(ctx))  # type: ignore[arg-type]

    assert room.sent[0][0] == AGENT_ERROR_TOPIC
    assert ctx.stopped == "agent error"


def test_an_error_waits_for_someone_to_join_before_it_is_sent() -> None:
    room = FakeRoom()
    room.remote_participants = {}

    async def run() -> None:
        sending = asyncio.create_task(
            worker.report_failure(room, RuntimeError("down"))  # type: ignore[arg-type]
        )
        await asyncio.sleep(0.05)
        assert room.sent == []
        for joined in room.joiners:
            joined(object())
        await sending

    asyncio.run(run())

    assert room.sent[0][0] == AGENT_ERROR_TOPIC


def test_the_worker_keeps_one_warm_job_process_not_one_per_cpu() -> None:
    assert worker.server._num_idle_processes == 1  # pyright: ignore[reportPrivateUsage]
