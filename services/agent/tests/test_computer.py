import asyncio
import json
from typing import Any, cast

import httpx
import pytest
from agent_fakes import DesktopFakeRoom, FakeRoom, knowledge_over
from google.genai import errors, types
from kb_agent import computer
from kb_agent.computer import (
    STEP_LIMIT,
    Approvals,
    ComputerTask,
    Desktop,
    Unsupported,
    step_for,
)
from kb_agent.support import NO_COMPUTER, SupportAgent
from kb_rag.testing import HASH_SETTINGS
from livekit import rtc
from qdrant_client import AsyncQdrantClient

USER = "user:abc"


def call(name: str, **args: Any) -> types.FunctionCall:
    return types.FunctionCall(id=f"call-{name}", name=name, args=args)


def reply(*calls: types.FunctionCall) -> types.Content:
    return types.Content(
        role="model", parts=[types.Part(function_call=c) for c in calls]
    )


CLICK = call("click", x=322, y=528, intent="Click Update card")
DONE = call("yield_to_user", reason="The card form is open.")


class Script:
    """Stands in for Gemini: answers each turn with the next scripted reply."""

    def __init__(self, *replies: types.Content, forever: types.Content | None = None):
        self.replies = list(replies)
        self.forever = forever
        self.turns: list[list[types.Content]] = []

    async def __call__(self, contents: list[types.Content]) -> types.Content:
        self.turns.append(list(contents))
        if self.replies:
            return self.replies.pop(0)
        assert self.forever is not None
        return self.forever


class Api:
    def __init__(self, status: int = 204) -> None:
        self.status = status
        self.events: list[dict[str, Any]] = []
        self.client = httpx.AsyncClient(
            transport=httpx.MockTransport(self.answer), base_url="http://api.test"
        )

    def answer(self, request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/internal/desktop-actions"
        self.events.append(json.loads(request.content))
        return httpx.Response(self.status)

    def names(self) -> list[str]:
        return [event["event"] for event in self.events]


def run_task(
    room: DesktopFakeRoom, plan: Script, api: Api | None = None
) -> tuple[str, list[str]]:
    said: list[str] = []

    async def say(message: str) -> None:
        said.append(message)

    async def go() -> str:
        task = ComputerTask(
            room=room,
            desktop=Desktop(room, room.helper),
            approvals=Approvals(USER),
            plan=plan,
            api=(api or Api()).client,
            say=say,
            agent_name="Shawn",
        )
        return await task.run("Open the card form", ())

    return asyncio.run(go()), said


def published(room: FakeRoom, topic: str) -> list[dict[str, object]]:
    return [body for sent, body in room.sent if sent == topic]


@pytest.fixture(autouse=True)
def quick(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(computer, "APPROVAL_SECONDS", 0.2)


def test_an_approved_click_runs_once_and_every_step_is_audited() -> None:
    room = DesktopFakeRoom()
    room.answers = [(USER, "once")]
    api = Api()

    said, narration = run_task(room, Script(reply(CLICK), reply(DONE)), api)

    assert said == "Handed back to the user: The card form is open."
    assert room.actions() == ["desktop.click"]
    assert ("desktop.click", {"x": 322, "y": 528}) in room.rpcs
    [proposal] = published(room, "computer")[:1]
    assert proposal["description"] == "Click Update card"
    assert (proposal["x"], proposal["y"], proposal["needs_approval"]) == (
        0.322,
        0.528,
        True,
    )
    assert published(room, "hud") == [
        {"kind": "clicking", "x": 0.322, "y": 0.528, "label": "Click Update card"}
    ]
    assert published(room, "computer")[-1]["kind"] == "ended"
    assert api.names() == ["proposed", "approved", "performed", "ended"]
    assert narration == ["Asking the user to allow on screen: Click Update card"]
    states = [body["state"] for method, body in room.rpcs if method == "desktop.cursor"]
    assert states[-3:] == ["clicking", "thinking", "hidden"]
    assert "about-to-click" in states


def test_an_answer_that_comes_before_the_agent_waits_still_counts() -> None:
    """The live run lost it: the user answered while the agent was still
    moving the cursor to the target."""
    room = DesktopFakeRoom()
    room.answers = [(USER, "once")]
    room.answer_after = 0

    said, _ = run_task(room, Script(reply(CLICK), reply(DONE)))

    assert said.startswith("Handed back")
    assert room.actions() == ["desktop.click"]


def test_allow_for_this_task_skips_the_wait_for_later_steps() -> None:
    room = DesktopFakeRoom()
    room.answers = [(USER, "task")]
    typing = call("type", text="4242", press_enter=True, intent="Type the seats")

    said, _ = run_task(room, Script(reply(CLICK), reply(typing), reply(DONE)))

    assert said.startswith("Handed back")
    assert room.actions() == ["desktop.click", "desktop.type", "desktop.key"]
    proposals = published(room, "computer")[:-1]
    assert [p["needs_approval"] for p in proposals] == [True, False]
    # The tray shows exactly what is typed, not only what the model intends.
    assert proposals[1]["description"] == (
        'Type the seats: types "4242" and presses enter'
    )


@pytest.mark.parametrize(
    ("answers", "outcome"),
    [
        ([(USER, "stop")], "The user stopped the task."),
        ([], "did not answer within a minute"),
        ([("desktop:abc", "once")], "did not answer within a minute"),
        ([("user:someone-else", "once")], "did not answer within a minute"),
    ],
)
def test_nothing_runs_without_an_approval_from_the_user(
    answers: list[tuple[str, str]], outcome: str
) -> None:
    room = DesktopFakeRoom()
    room.answers = answers
    api = Api()

    said, _ = run_task(room, Script(reply(CLICK), reply(DONE)), api)

    assert outcome in said
    assert room.actions() == []
    assert published(room, "hud") == []
    assert "performed" not in api.names()
    assert published(room, "computer")[-1]["kind"] == "ended"


def test_a_stop_during_an_allowed_task_ends_it_before_the_next_step() -> None:
    room = DesktopFakeRoom()
    room.answers = [(USER, "task")]
    second = call("click", x=10, y=10, intent="Click Save")

    async def stop_after_first(contents: list[types.Content]) -> types.Content:
        if len(contents) > 2:
            first = published(room, "computer")[0]
            room.decide(USER, str(first["id"]), "stop")
            return reply(second)
        return reply(CLICK)

    said, _ = run_task(room, cast(Script, stop_after_first))
    assert "Click Save" not in str(published(room, "computer"))

    assert said == "The user stopped the task."
    assert room.actions() == ["desktop.click"]


def test_a_safety_confirmation_always_waits_and_is_acknowledged() -> None:
    room = DesktopFakeRoom()
    room.answers = [(USER, "task"), (USER, "once")]
    risky = call(
        "click",
        x=500,
        y=500,
        intent="Click Delete account",
        safety_decision={
            "decision": "require_confirmation",
            "explanation": "This deletes data.",
        },
    )
    plan = Script(reply(CLICK), reply(risky), reply(DONE))

    run_task(room, plan)

    proposals = published(room, "computer")[:-1]
    assert [p["needs_approval"] for p in proposals] == [True, True]
    assert proposals[1]["warning"] == "This deletes data."
    answered = plan.turns[-1][-1].parts or []
    response = answered[0].function_response
    assert response is not None and response.response is not None
    assert response.response["safety_acknowledgement"] is True
    assert room.actions() == ["desktop.click", "desktop.click"]


def test_a_blocked_step_ends_the_task_without_acting() -> None:
    room = DesktopFakeRoom()
    blocked = call(
        "click", x=1, y=1, safety_decision={"decision": "blocked", "explanation": "No"}
    )

    said, _ = run_task(room, Script(reply(blocked)))

    assert "safety check blocked" in said
    assert room.actions() == []


def test_the_task_stops_at_the_step_limit() -> None:
    room = DesktopFakeRoom()
    room.answers = [(USER, "task")]
    plan = Script(forever=reply(CLICK))

    said, _ = run_task(room, plan)

    assert said == f"Stopped after {STEP_LIMIT} steps without finishing."
    assert len(plan.turns) == STEP_LIMIT
    assert room.actions() == ["desktop.click"] * STEP_LIMIT


def test_each_result_goes_back_with_a_fresh_screenshot() -> None:
    room = DesktopFakeRoom()
    room.answers = [(USER, "once")]
    plan = Script(reply(CLICK), reply(DONE))

    run_task(room, plan)

    first = plan.turns[0][0].parts or []
    assert first[1].inline_data is not None
    assert first[1].inline_data.data == DesktopFakeRoom.SCREEN
    response = (plan.turns[1][-1].parts or [])[0].function_response
    assert response is not None and response.parts is not None
    blob = response.parts[0].inline_data
    assert blob is not None and blob.data == DesktopFakeRoom.SCREEN
    assert response.response == {"result": "ok"}


def test_an_unsupported_action_is_explained_to_the_model_not_run() -> None:
    room = DesktopFakeRoom()
    plan = Script(reply(call("drag_and_drop", start_x=1)), reply(DONE))

    run_task(room, plan)

    response = (plan.turns[1][-1].parts or [])[0].function_response
    assert response is not None and response.response is not None
    assert "not available" in response.response["error"]
    assert room.actions() == []


def test_a_helper_error_goes_back_to_the_model() -> None:
    room = DesktopFakeRoom()
    room.answers = [(USER, "once")]
    room.failing["desktop.click"] = rtc.RpcError(4002, "desktop.click failed: busy")
    plan = Script(reply(CLICK), reply(DONE))
    api = Api()

    run_task(room, plan, api)

    response = (plan.turns[1][-1].parts or [])[0].function_response
    assert response is not None and response.response is not None
    assert response.response == {"error": "desktop.click failed: busy"}
    assert "failed" in api.names()


def test_a_gemini_outage_ends_the_task_and_says_so() -> None:
    room = DesktopFakeRoom()

    async def unavailable(contents: list[types.Content]) -> types.Content:
        raise errors.ServerError(503, {"error": {"message": "Deadline expired"}})

    said, _ = run_task(room, cast(Script, unavailable))

    assert said.startswith("The task stopped because something failed (ServerError)")
    assert room.actions() == []
    assert published(room, "computer")[-1] == {
        "kind": "ended",
        "task": published(room, "computer")[-1]["task"],
        "reason": "failed",
    }


def test_an_audit_log_that_cannot_record_stops_the_task_before_it_acts() -> None:
    room = DesktopFakeRoom()
    room.answers = [(USER, "once")]

    said, _ = run_task(room, Script(reply(CLICK), reply(DONE)), Api(status=503))

    assert "something failed" in said
    assert room.actions() == []
    assert room.streams == {} and room.listeners == []


@pytest.mark.parametrize(
    ("fc", "rpcs"),
    [
        (
            call("double_click", x=1, y=2),
            [("desktop.click", {"x": 1, "y": 2, "double": True})],
        ),
        (
            call("right_click", x=1, y=2),
            [("desktop.click", {"x": 1, "y": 2, "button": "right"})],
        ),
        (call("type", text="hi"), [("desktop.type", {"text": "hi"})]),
        (call("press_key", key="Return"), [("desktop.key", {"keys": ["enter"]})]),
        (
            call("press_key", key="Control+C"),
            [("desktop.key", {"keys": ["ctrl", "c"]})],
        ),
        (
            call("hotkey", keys=["Meta", "Shift", "T"]),
            [("desktop.key", {"keys": ["cmd", "shift", "t"]})],
        ),
        (
            call("scroll", x=5, y=6, direction="up", magnitude_in_pixels=400),
            [("desktop.scroll", {"x": 5, "y": 6, "dy": -10})],
        ),
        (
            call("scroll", x=5, y=6, direction="right"),
            [("desktop.scroll", {"x": 5, "y": 6, "dx": 8})],
        ),
        (call("wait", seconds=2), []),
        (call("take_screenshot"), []),
    ],
)
def test_computer_use_calls_map_to_helper_calls(
    fc: types.FunctionCall, rpcs: list[tuple[str, dict[str, object]]]
) -> None:
    assert step_for(fc).rpcs == rpcs


@pytest.mark.parametrize(
    "fc",
    [
        call("click", x=1000, y=5),
        call("click", x=5),
        call("scroll", x=5, y=5, direction="sideways"),
        call("hotkey", keys="cmd+c"),
        call("navigate", url="https://example.com"),
    ],
)
def test_calls_the_helper_cannot_run_are_refused(fc: types.FunctionCall) -> None:
    with pytest.raises(Unsupported):
        step_for(fc)


def agent(room: FakeRoom, user: str | None) -> SupportAgent:
    return SupportAgent(
        instructions="You are Shawn.",
        knowledge=knowledge_over(AsyncQdrantClient(":memory:"), HASH_SETTINGS),
        room=room,
        api_url="http://api.test",
        user=user,
    )


@pytest.mark.parametrize(
    ("room", "user"),
    [
        (DesktopFakeRoom(helper=False), USER),
        (DesktopFakeRoom(), None),
        (DesktopFakeRoom(), "api_key:k1"),
        (FakeRoom(), USER),
    ],
)
def test_without_a_connected_mac_the_agent_offers_to_guide_instead(
    room: FakeRoom, user: str | None
) -> None:
    async def run() -> str:
        tool = cast(Any, agent(room, user).operate_computer)
        return await tool(None, "Open billing")

    assert asyncio.run(run()) == NO_COMPUTER
    assert "point_at" in NO_COMPUTER
    assert getattr(room, "rpcs", []) == []
