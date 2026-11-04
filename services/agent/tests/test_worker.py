import asyncio
import json
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
from agent_fakes import FakeRoom, ScreenRoom
from kb_agent import worker
from kb_agent.product import (
    fetch_product,
    product_from_body,
    product_id_from_metadata,
    user_from_metadata,
)
from kb_agent.prompt import render_system_prompt
from kb_agent.protocol import (
    AGENT_ERROR_TOPIC,
    KB_PHASE_LIVE,
    KB_PHASE_WAITING_FOR_SCREEN,
    NO_SCREEN_MESSAGE,
)
from livekit import rtc

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

    product = fetch_product(api_url, product_id_from_metadata(metadata))
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
        fetch_product(api_url, "00000000-0000-0000-0000-000000000000")


def test_dispatch_metadata_names_the_user_when_the_api_sends_one() -> None:
    named = json.dumps({"product_id": PRODUCT_ID, "user": "user:abc"})

    assert user_from_metadata(named) == "user:abc"
    assert user_from_metadata(json.dumps({"product_id": PRODUCT_ID})) is None
    assert user_from_metadata(json.dumps({"product_id": PRODUCT_ID, "user": 7})) is None


class _Job:
    metadata = json.dumps({"product_id": PRODUCT_ID})


class _Ctx:
    def __init__(self, room: ScreenRoom) -> None:
        self.room = room
        self.job = _Job()
        self.stopped: str | None = None

    async def connect(self) -> None:
        return None

    def shutdown(self, reason: str = "") -> None:
        self.stopped = reason

    def add_shutdown_callback(self, callback: object) -> None:
        return None


SCREEN = rtc.TrackSource.SOURCE_SCREENSHARE
CAMERA = rtc.TrackSource.SOURCE_CAMERA


class _Session:
    """Records the agent's phase at the moment the model would connect."""

    def __init__(self, room: ScreenRoom) -> None:
        self.room = room
        self.started_in: str | None = None

    def on(self, event: str, callback: object = None) -> object:
        return callback or (lambda handler: handler)

    async def start(self, **kwargs: object) -> None:
        self.started_in = self.room.phases[-1]


@pytest.fixture
def sharing(
    api_url: str, monkeypatch: pytest.MonkeyPatch
) -> tuple[ScreenRoom, _Ctx, _Session]:
    """A dispatch for user:abc, who is in the room and has not shared yet."""
    monkeypatch.setenv("API_URL", api_url)
    room = ScreenRoom("user:abc")
    session = _Session(room)
    monkeypatch.setattr(worker, "build_session", lambda voice, sampler: session)
    ctx = _Ctx(room)
    ctx.job.metadata = json.dumps({"product_id": PRODUCT_ID, "user": "user:abc"})
    return room, ctx, session


def run_entrypoint(ctx: _Ctx, room: ScreenRoom, act: Callable[[], None]) -> None:
    """Run the job, and act once it waits for the screen share."""

    async def run() -> None:
        job = asyncio.create_task(worker.entrypoint(ctx))  # type: ignore[arg-type]
        for _ in range(200):
            if room.handlers.get("track_published") or job.done():
                break
            await asyncio.sleep(0.01)
        act()
        await job

    asyncio.run(run())


def test_the_session_starts_at_once_when_the_screen_is_already_shared(
    sharing: tuple[ScreenRoom, _Ctx, _Session],
) -> None:
    room, ctx, session = sharing
    room.publish_track("user:abc", SCREEN)

    run_entrypoint(ctx, room, lambda: None)

    assert room.phases == [KB_PHASE_WAITING_FOR_SCREEN, KB_PHASE_LIVE]
    assert session.started_in == KB_PHASE_LIVE
    assert room.sent == []


def test_the_model_waits_until_the_user_shares_their_screen(
    sharing: tuple[ScreenRoom, _Ctx, _Session],
) -> None:
    room, ctx, session = sharing
    seen_before: list[str | None] = []

    def share() -> None:
        seen_before.append(session.started_in)
        seen_before.append(room.phases[-1])
        room.publish_track("user:abc", SCREEN)

    run_entrypoint(ctx, room, share)

    assert seen_before == [None, KB_PHASE_WAITING_FOR_SCREEN]
    assert room.phases == [KB_PHASE_WAITING_FOR_SCREEN, KB_PHASE_LIVE]
    assert session.started_in == KB_PHASE_LIVE


def test_a_camera_or_someone_elses_screen_does_not_start_the_model(
    sharing: tuple[ScreenRoom, _Ctx, _Session],
) -> None:
    room, ctx, session = sharing
    seen_before: list[str | None] = []

    def share_the_wrong_things() -> None:
        room.join("desktop:abc")
        room.publish_track("desktop:abc", SCREEN)
        room.publish_track("user:abc", CAMERA)
        seen_before.append(session.started_in)
        room.publish_track("user:abc", SCREEN)

    run_entrypoint(ctx, room, share_the_wrong_things)

    assert seen_before == [None]
    assert session.started_in == KB_PHASE_LIVE


def test_no_screen_in_time_tells_the_user_and_ends_the_job(
    sharing: tuple[ScreenRoom, _Ctx, _Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    room, ctx, session = sharing
    monkeypatch.setattr(worker, "SCREEN_WAIT_SECONDS", 0.05)

    run_entrypoint(ctx, room, lambda: room.publish_track("user:abc", CAMERA))

    assert room.sent == [(AGENT_ERROR_TOPIC, {"message": NO_SCREEN_MESSAGE})]
    assert ctx.stopped == "no screen share"
    assert session.started_in is None
    assert room.phases == [KB_PHASE_WAITING_FOR_SCREEN]


def test_a_user_who_leaves_before_sharing_ends_the_job_quietly(
    sharing: tuple[ScreenRoom, _Ctx, _Session],
) -> None:
    room, ctx, session = sharing

    run_entrypoint(ctx, room, lambda: room.leave("user:abc"))

    assert room.sent == []
    assert ctx.stopped == "user left"
    assert session.started_in is None


def test_without_a_named_user_the_first_participant_must_share() -> None:
    room = ScreenRoom("user:abc")
    room.join("desktop:abc")

    async def run() -> str:
        waiting = asyncio.create_task(
            worker.wait_for_screen(room, None, 1)  # type: ignore[arg-type]
        )
        await asyncio.sleep(0)
        room.publish_track("desktop:abc", SCREEN)
        await asyncio.sleep(0)
        assert not waiting.done()
        room.publish_track("user:abc", SCREEN)
        return await waiting

    assert asyncio.run(run()) == "shared"
    assert room.handlers == {
        "participant_connected": [],
        "track_published": [],
        "participant_disconnected": [],
    }


class _BrokenSession:
    def on(self, event: str, callback: object = None) -> object:
        return callback or (lambda handler: handler)

    async def start(self, **kwargs: object) -> None:
        raise RuntimeError("model refused the connection")


def test_a_model_that_cannot_start_tells_the_room_why(
    api_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("API_URL", api_url)
    room = ScreenRoom()
    room.publish_track("user:abc", SCREEN)
    voices: list[str] = []

    def broken(voice: str, sampler: object) -> _BrokenSession:
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
    api_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("API_URL", api_url)
    room = ScreenRoom()
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
