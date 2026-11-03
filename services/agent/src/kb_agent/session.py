import asyncio
from collections.abc import Callable

from google.genai import types
from livekit.agents import (
    AgentSession,
    ConversationItemAddedEvent,
    MetricsCollectedEvent,
    room_io,
)
from livekit.agents.llm import ChatMessage
from livekit.agents.voice import VoiceActivityVideoSampler
from livekit.plugins import google

from kb_agent.latency import component_latency, log_json, turn_latency
from kb_agent.turns import TurnLog

MODEL = "gemini-3.8-live-extended-thinking"
DEFAULT_MAX_SESSION_SECONDS = 600
GOODBYE = (
    "The session time limit is reached. Say a short goodbye in one sentence "
    "and tell the user they can start a new session."
)
GOODBYE_TIMEOUT_SECONDS = 20


def build_session(voice: str) -> AgentSession:
    model = google.realtime.RealtimeModel(
        model=MODEL,
        voice=voice,
        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
        media_resolution=types.MediaResolution.MEDIA_RESOLUTION_MEDIUM,
    )
    # One frame a second while the user speaks, one per three seconds otherwise.
    return AgentSession(
        llm=model,
        video_sampler=VoiceActivityVideoSampler(speaking_fps=1.0, silent_fps=0.3),
    )


def room_options(user: str | None) -> room_io.RoomOptions:
    # Without video_input the worker never subscribes to the screen share.
    if user is None:
        return room_io.RoomOptions(video_input=True)
    # Pinned, so a desktop helper that joins first is never taken for the user.
    return room_io.RoomOptions(video_input=True, participant_identity=user)


def max_session_seconds(raw: str | None) -> int:
    if not raw:
        return DEFAULT_MAX_SESSION_SECONDS
    seconds = int(raw)
    if seconds < 1:
        raise ValueError("AGENT_MAX_SESSION_SECONDS must be at least 1")
    return seconds


async def enforce_time_limit(
    session: AgentSession,
    seconds: float,
    on_limit: Callable[[], None],
) -> None:
    """Say goodbye once the limit passes, then close the session."""
    await asyncio.sleep(seconds)
    log_json({"event": "session_limit", "seconds": seconds})
    try:
        await asyncio.wait_for(
            session.generate_reply(instructions=GOODBYE), GOODBYE_TIMEOUT_SECONDS
        )
    except Exception as exc:
        # The limit holds even when the goodbye cannot be spoken.
        log_json({"event": "goodbye_failed", "error": type(exc).__name__})
    on_limit()


def attach_logs(session: AgentSession, turns: TurnLog) -> None:
    def on_metrics(ev: MetricsCollectedEvent) -> None:
        record = component_latency(ev.metrics)
        if record is not None:
            log_json(record)
            turns.on_metrics(record)

    def on_item(ev: ConversationItemAddedEvent) -> None:
        if isinstance(ev.item, ChatMessage):
            record = turn_latency(ev.item.role, ev.item.metrics)
            if record is not None:
                log_json(record)

    session.on("metrics_collected", on_metrics)
    session.on("conversation_item_added", on_item)
