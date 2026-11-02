import asyncio
import json
import sys
from collections.abc import Callable, Coroutine
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import kb_desktop
import pytest
from kb_desktop import main as helper
from kb_desktop.actions import METHODS, Action, Click, Display
from livekit import rtc

AGENT = rtc.ParticipantKind.PARTICIPANT_KIND_AGENT
STANDARD = rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD
DISPLAY = Display(width=1000, height=500, scale=1.0)

Handler = Callable[[rtc.RpcInvocationData], Coroutine[Any, Any, str]]


def room_with(*participants: tuple[str, int]) -> tuple[rtc.Room, dict[str, Handler]]:
    handlers: dict[str, Handler] = {}
    room = SimpleNamespace(
        remote_participants={
            identity: SimpleNamespace(kind=kind) for identity, kind in participants
        },
        local_participant=SimpleNamespace(
            register_rpc_method=lambda method, handler: handlers.update(
                {method: handler}
            )
        ),
    )
    return cast(rtc.Room, room), handlers


def call(handlers: dict[str, Handler], method: str, caller: str, payload: str) -> str:
    invocation = rtc.RpcInvocationData(
        request_id="r1", caller_identity=caller, payload=payload, response_timeout=5
    )
    return asyncio.run(handlers[method](invocation))


def test_every_method_is_registered() -> None:
    room, handlers = room_with()
    helper.register(room, lambda: DISPLAY, lambda action, display: None)

    assert set(handlers) == set(METHODS)


def test_the_agent_can_act() -> None:
    done: list[Action] = []
    room, handlers = room_with(("agent-1", AGENT))
    helper.register(room, lambda: DISPLAY, lambda action, display: done.append(action))

    reply = call(handlers, "desktop.click", "agent-1", '{"x": 500, "y": 500}')

    assert json.loads(reply) == {"ok": True}
    assert done == [Click(x=500, y=500)]


@pytest.mark.parametrize("caller", ["user:abc", "someone-who-left"])
def test_everyone_else_is_refused(caller: str) -> None:
    done: list[Action] = []
    room, handlers = room_with(("user:abc", STANDARD))
    helper.register(room, lambda: DISPLAY, lambda action, display: done.append(action))

    with pytest.raises(rtc.RpcError) as refused:
        call(handlers, "desktop.click", caller, '{"x": 1, "y": 1}')

    assert refused.value.code == helper.FORBIDDEN
    assert done == []


def test_a_bad_payload_comes_back_as_a_clear_rpc_error() -> None:
    room, handlers = room_with(("agent-1", AGENT))
    helper.register(room, lambda: DISPLAY, lambda action, display: None)

    with pytest.raises(rtc.RpcError) as bad:
        call(handlers, "desktop.key", "agent-1", '{"keys": ["cmd", "banana"]}')

    assert bad.value.code == helper.INVALID_REQUEST
    assert "unknown keys ['banana']" in bad.value.message


def test_an_executor_failure_comes_back_as_an_rpc_error() -> None:
    def broken(action: Action, display: Display) -> None:
        raise RuntimeError("macOS refused to create the input event")

    room, handlers = room_with(("agent-1", AGENT))
    helper.register(room, lambda: DISPLAY, broken)

    with pytest.raises(rtc.RpcError) as failed:
        call(handlers, "desktop.type", "agent-1", '{"text": "hi"}')

    assert failed.value.code == helper.FAILED
    assert "macOS refused" in failed.value.message


@pytest.fixture
def fake_mac(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Stands in for the macOS module so these tests run anywhere."""
    mac = SimpleNamespace(
        trusted=True,
        executed=[],
        accessibility_trusted=lambda: mac.trusted,
        main_display=lambda: DISPLAY,
        execute=lambda action, display: mac.executed.append(action),
    )
    monkeypatch.setitem(sys.modules, "kb_desktop.mac", cast(ModuleType, mac))
    monkeypatch.setattr(kb_desktop, "mac", mac, raising=False)
    return mac


def start(
    monkeypatch: pytest.MonkeyPatch, *flags: str
) -> list[Callable[[Action, Display], None]]:
    executors: list[Callable[[Action, Display], None]] = []

    async def run(url, token, display, executor) -> None:
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


def test_a_refused_token_is_reported_without_a_traceback(
    fake_mac: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def refuse(url, token, display, executor) -> None:
        raise rtc.ConnectError("401 Unauthorized")

    monkeypatch.setattr(helper, "run", refuse)

    assert helper.main(["--url", "ws://x", "--token", "old"]) == 1
    assert "401 Unauthorized" in capsys.readouterr().out
