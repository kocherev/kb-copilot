import asyncio
import json
from collections.abc import Mapping
from typing import Protocol

import livekit.rtc as rtc
from livekit.agents import AgentSession
from livekit.agents.voice import AgentStateChangedEvent

from kb_agent.latency import log_json

HUD_TOPIC = "hud"
_LABEL_LIMIT = 80


class _HudPublisher(Protocol):
    async def publish_data(
        self,
        payload: bytes,
        *,
        reliable: bool = True,
        topic: str = "",
    ) -> None: ...


class _HudRoom(Protocol):
    def isconnected(self) -> bool: ...

    @property
    def local_participant(self) -> _HudPublisher: ...


def point_payload(x: float, y: float, label: str) -> dict[str, object]:
    text = " ".join(label.split())[:_LABEL_LIMIT] or "Here"
    return {
        "kind": "point",
        "x": _unit(x),
        "y": _unit(y),
        "label": text,
    }


def thinking_payload(active: bool) -> dict[str, object]:
    return {"kind": "thinking", "active": active}


async def publish_hud(room: _HudRoom, payload: Mapping[str, object]) -> None:
    if not room.isconnected():
        return
    body = json.dumps(payload, sort_keys=True).encode()
    await room.local_participant.publish_data(body, reliable=True, topic=HUD_TOPIC)
    log_json({"event": "hud", "kind": payload.get("kind", "")})


def bind_screen_hud(session: AgentSession, room: rtc.Room) -> None:
    @session.on("agent_state_changed")
    def on_state(ev: AgentStateChangedEvent) -> None:
        # The preview pulse follows thinking. It is not an OS cursor.
        _schedule(room, thinking_payload(ev.new_state == "thinking"))


def _schedule(room: rtc.Room, payload: Mapping[str, object]) -> None:
    task = asyncio.get_running_loop().create_task(publish_hud(room, payload))

    def _done(finished: asyncio.Task[None]) -> None:
        if finished.cancelled():
            return
        error = finished.exception()
        if error is not None:
            log_json(
                {
                    "event": "hud",
                    "published": False,
                    "error": type(error).__name__,
                }
            )

    task.add_done_callback(_done)


def _unit(value: float) -> float:
    if value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return round(value, 4)
