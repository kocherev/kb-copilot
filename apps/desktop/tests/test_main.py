import asyncio
import json
import sys
from collections.abc import Callable, Coroutine
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import kb_desktop
import pytest
from kb_desktop import main as helper
from kb_desktop.actions import METHODS, Action, Click, Cursor, Display
from livekit import rtc

AGENT = rtc.ParticipantKind.PARTICIPANT_KIND_AGENT
STANDARD = rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD
DISPLAY = Display(width=1000, height=500, scale=1.0)

Handler = Callable[[rtc.RpcInvocationData], Coroutine[Any, Any, str]]


PNG = b"\x89PNG fake screen"


@pytest.fixture(autouse=True)
def short_join_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(helper, "JOIN_WAIT_SECONDS", 0.2)


def room_with(*participants: tuple[str, int]) -> tuple[rtc.Room, dict[str, Handler]]:
    handlers: dict[str, Handler] = {}
    streams: list[dict[str, object]] = []

    async def send_bytes(data: bytes, **options: object) -> None:
        streams.append({"data": data, **options})

    room = SimpleNamespace(
        remote_participants={
            identity: SimpleNamespace(kind=kind) for identity, kind in participants
        },
        local_participant=SimpleNamespace(
            register_rpc_method=lambda method, handler: handlers.update(
                {method: handler}
            ),
            send_bytes=send_bytes,
        ),
        streams=streams,
    )
    return cast(rtc.Room, room), handlers


def register(
    room: rtc.Room,
    executor: Callable[[Action, Display], None] = lambda action, display: None,
    shown: list[Cursor] | None = None,
) -> None:
    helper.register(
        room,
        lambda: DISPLAY,
        executor,
        lambda display: PNG,
        lambda command, display: (shown if shown is not None else []).append(command),
    )


def call(handlers: dict[str, Handler], method: str, caller: str, payload: str) -> str:
    invocation = rtc.RpcInvocationData(
        request_id="r1", caller_identity=caller, payload=payload, response_timeout=5
    )
    return asyncio.run(handlers[method](invocation))


def test_every_method_is_registered() -> None:
    room, handlers = room_with()
    register(room)

    assert set(handlers) == set(METHODS) | {"desktop.screenshot", "desktop.cursor"}


def test_the_agent_can_act() -> None:
    done: list[Action] = []
    room, handlers = room_with(("agent-1", AGENT))
    register(room, lambda action, display: done.append(action))

    reply = call(handlers, "desktop.click", "agent-1", '{"x": 500, "y": 500}')

    assert json.loads(reply) == {"ok": True}
    assert done == [Click(x=500, y=500)]


def test_an_agent_whose_join_has_not_arrived_yet_is_waited_for() -> None:
    """A call can outrun the participant event. That race made the live test flaky."""
    done: list[Action] = []
    room, handlers = room_with()
    register(room, lambda action, display: done.append(action))

    async def join_then_call() -> str:
        async def join_late() -> None:
            await asyncio.sleep(0.05)
            cast(dict[str, object], room.remote_participants)["agent-1"] = (
                SimpleNamespace(kind=AGENT)
            )

        joining = asyncio.create_task(join_late())
        reply = await handlers["desktop.click"](
            rtc.RpcInvocationData(
                request_id="r1",
                caller_identity="agent-1",
                payload='{"x": 1, "y": 2}',
                response_timeout=5,
            )
        )
        await joining
        return reply

    assert json.loads(asyncio.run(join_then_call())) == {"ok": True}
    assert done == [Click(x=1, y=2)]


def test_a_screenshot_streams_to_the_caller_and_the_reply_stays_small() -> None:
    room, handlers = room_with(("agent-1", AGENT))
    register(room)

    reply = call(handlers, "desktop.screenshot", "agent-1", '{"stream_id": "shot-1"}')

    assert json.loads(reply) == {"bytes": len(PNG)}
    assert room.streams == [  # type: ignore[attr-defined]
        {
            "data": PNG,
            "topic": helper.SCREENSHOT_TOPIC,
            "stream_id": "shot-1",
            "mime_type": "image/png",
            "destination_identities": ["agent-1"],
        }
    ]


def test_the_cursor_method_shows_the_command() -> None:
    shown: list[Cursor] = []
    room, handlers = room_with(("agent-1", AGENT))
    register(room, shown=shown)
    payload = {
        "state": "about-to-click",
        "x": 10,
        "y": 20,
        "name": "Shawn",
        "label": "Update card",
    }

    reply = call(handlers, "desktop.cursor", "agent-1", json.dumps(payload))

    assert json.loads(reply) == {"ok": True}
    assert shown == [Cursor.model_validate(payload)]


@pytest.mark.parametrize("caller", ["user:abc", "someone-who-left"])
@pytest.mark.parametrize(
    ("method", "payload"),
    [
        ("desktop.click", '{"x": 1, "y": 1}'),
        ("desktop.screenshot", '{"stream_id": "s"}'),
        ("desktop.cursor", '{"state": "hidden", "x": 1, "y": 1, "name": "Shawn"}'),
    ],
)
def test_everyone_else_is_refused(caller: str, method: str, payload: str) -> None:
    done: list[Action] = []
    shown: list[Cursor] = []
    room, handlers = room_with(("user:abc", STANDARD))
    register(room, lambda action, display: done.append(action), shown)

    with pytest.raises(rtc.RpcError) as refused:
        call(handlers, method, caller, payload)

    assert refused.value.code == helper.FORBIDDEN
    assert done == []
    assert shown == []
    assert room.streams == []  # type: ignore[attr-defined]


def test_a_bad_payload_comes_back_as_a_clear_rpc_error() -> None:
    room, handlers = room_with(("agent-1", AGENT))
    register(room)

    with pytest.raises(rtc.RpcError) as bad:
        call(handlers, "desktop.key", "agent-1", '{"keys": ["cmd", "banana"]}')
    with pytest.raises(rtc.RpcError) as no_id:
        call(handlers, "desktop.screenshot", "agent-1", "{}")

    assert bad.value.code == helper.INVALID_REQUEST
    assert "unknown keys ['banana']" in bad.value.message
    assert no_id.value.code == helper.INVALID_REQUEST
    assert "stream_id: Field required" in no_id.value.message


def test_an_executor_failure_comes_back_as_an_rpc_error() -> None:
    def broken(action: Action, display: Display) -> None:
        raise RuntimeError("macOS refused to create the input event")

    room, handlers = room_with(("agent-1", AGENT))
    register(room, broken)

    with pytest.raises(rtc.RpcError) as failed:
        call(handlers, "desktop.type", "agent-1", '{"text": "hi"}')

    assert failed.value.code == helper.FAILED
    assert "macOS refused" in failed.value.message


@pytest.fixture
def fake_mac(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Stands in for the macOS module so these tests run anywhere."""
    mac = SimpleNamespace(
        trusted=True,
        recording=True,
        asked=[],
        executed=[],
        accessibility_trusted=lambda: mac.trusted,
        screen_recording_allowed=lambda: mac.recording,
        ask_for_screen_recording=lambda: mac.asked.append(True),
        main_display=lambda: DISPLAY,
        execute=lambda action, display: mac.executed.append(action),
        capture=lambda display: PNG,
    )
    overlay = SimpleNamespace(start=lambda: lambda command, display: None)
    for name, module in (("mac", mac), ("overlay", overlay)):
        monkeypatch.setitem(sys.modules, f"kb_desktop.{name}", cast(ModuleType, module))
        monkeypatch.setattr(kb_desktop, name, module, raising=False)
    return mac


def start(
    monkeypatch: pytest.MonkeyPatch, *flags: str
) -> list[Callable[[Action, Display], None]]:
    executors: list[Callable[[Action, Display], None]] = []

    async def run(url, token, display, executor, capture, show_cursor) -> None:
        executors.append(executor)

    monkeypatch.setattr(helper, "run", run)
    helper.main(["--url", "ws://x", "--token", "t", *flags])
    return executors


def test_dry_run_logs_the_action_and_does_not_execute(
    fake_mac: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake_mac.trusted = False
    [executor] = start(monkeypatch, "--dry-run")

    with caplog.at_level("INFO", logger="kb_desktop"):
        executor(Click(x=500, y=500), DISPLAY)

    assert fake_mac.executed == []
    assert "at point (500, 250)" in caplog.text


def test_a_real_run_executes(
    fake_mac: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    [executor] = start(monkeypatch)

    executor(Click(x=10, y=20), DISPLAY)

    assert fake_mac.executed == [Click(x=10, y=20)]


def test_missing_accessibility_access_explains_where_to_grant_it(
    fake_mac: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_mac.trusted = False

    assert start(monkeypatch) == []
    assert helper.main(["--url", "ws://x", "--token", "t"]) == 1
    assert "System Settings > Privacy & Security > Accessibility" in (
        capsys.readouterr().out
    )


def test_missing_screen_recording_asks_and_explains_where_to_grant_it(
    fake_mac: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_mac.recording = False

    assert start(monkeypatch, "--dry-run") == []
    assert helper.main(["--url", "ws://x", "--token", "t", "--dry-run"]) == 1
    assert fake_mac.asked
    assert "Privacy & Security > Screen & System Audio Recording" in (
        capsys.readouterr().out
    )


def test_a_refused_token_is_reported_without_a_traceback(
    fake_mac: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def refuse(url, token, display, executor, capture, show_cursor) -> None:
        raise rtc.ConnectError("401 Unauthorized")

    monkeypatch.setattr(helper, "run", refuse)

    assert helper.main(["--url", "ws://x", "--token", "old"]) == 1
    assert "401 Unauthorized" in capsys.readouterr().out
