from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlparse

import livekit.rtc as rtc
from livekit.agents import (
    AgentSession,
    ConversationItemAddedEvent,
    MetricsCollectedEvent,
    inference,
    llm,
    room_io,
    stt,
    tts,
)
from livekit.agents.llm import ChatMessage
from livekit.agents.metrics import AgentMetrics
from livekit.agents.voice import VoiceActivityVideoSampler
from openai.types.realtime import RealtimeReasoning

from kb_agent.latency import component_latency, log_json, turn_latency

CLOUD_STT = "assemblyai/universal-3-6-pro"
CLOUD_TTS = "fishaudio/s2.1-pro"
CLOUD_TTS_VOICE = "fa4c9eb3dccc4806b382b40d61c6b10a"
CLOUD_VOICE = "Puck"
# Confirmed on the LiveKit Inference Gemini Live table.
# google/gemini-live is an alias of google/gemini-3.8-live.
REALTIME_CANDIDATES = (
    "google/gemini-3.8-live-extended-thinking",
    "google/gemini-3.8-live",
    "google/gemini-live",
)
EXTENDED_THINKING = REALTIME_CANDIDATES[0]
# One frame a second while the caller speaks, slower when they are quiet.
# Higher rates spend image tokens for little extra guidance.
VIDEO_SPEAKING_FPS = 1.0
VIDEO_SILENT_FPS = 0.3
OPENAI_STT = "gpt-4o-mini-transcribe"
OPENAI_LLM = "gpt-4.1-mini"
OPENAI_TTS = "gpt-4o-mini-tts"
OPENAI_VOICE = "ash"


def model_provider(livekit_url: str) -> str:
    host = (urlparse(livekit_url).hostname or "").lower().rstrip(".")
    if host == "livekit.cloud" or host.endswith(".livekit.cloud"):
        return "livekit"
    return "openai"


def voice_attempts(livekit_url: str) -> tuple[str | None, ...]:
    if model_provider(livekit_url) != "livekit":
        return (None,)
    return REALTIME_CANDIDATES


def resolve_realtime_model(requested: str | None) -> str:
    if requested is None:
        return EXTENDED_THINKING
    if requested not in REALTIME_CANDIDATES:
        raise ValueError(f"unsupported realtime model: {requested}")
    return requested


def session_room_options() -> room_io.RoomOptions:
    # RoomIO subscribes to screen-share video only when video input is enabled.
    # Frames are forwarded to a realtime model. The OpenAI pipeline does not
    # consume them.
    return room_io.RoomOptions(video_input=True)


def is_screen_share_video(source: int, kind: int) -> bool:
    screen = source == rtc.TrackSource.SOURCE_SCREENSHARE
    video = kind == rtc.TrackKind.KIND_VIDEO
    return screen and video


@dataclass
class VoiceStack:
    session: AgentSession
    provider: str
    realtime_model: str | None
    voice: str
    reasoning_effort: str | None
    video_speaking_fps: float | None
    video_silent_fps: float | None
    stt: stt.STT
    llm: llm.LLM | llm.RealtimeModel
    tts: tts.TTS


def build_voice(livekit_url: str, *, realtime_model: str | None = None) -> VoiceStack:
    if model_provider(livekit_url) == "livekit":
        return _cloud_voice(resolve_realtime_model(realtime_model))
    from livekit.plugins import openai

    speech = openai.STT(model=OPENAI_STT)
    model = openai.responses.LLM(model=OPENAI_LLM)
    voice = openai.TTS(model=OPENAI_TTS, voice=OPENAI_VOICE)
    return VoiceStack(
        session=AgentSession(stt=speech, llm=model, tts=voice),
        provider="openai",
        realtime_model=None,
        voice=OPENAI_VOICE,
        reasoning_effort=None,
        video_speaking_fps=None,
        video_silent_fps=None,
        stt=speech,
        llm=model,
        tts=voice,
    )


def _cloud_voice(model_id: str) -> VoiceStack:
    effort = "low" if model_id == EXTENDED_THINKING else None
    speech = inference.STT(model=CLOUD_STT, language="en")
    spoken = inference.TTS(model=CLOUD_TTS, voice=CLOUD_TTS_VOICE)
    model = inference.RealtimeModel(
        model=model_id,
        voice=CLOUD_VOICE,
        reasoning=RealtimeReasoning(effort="low") if effort else None,
    )
    activity = inference.VAD()
    session = AgentSession(
        stt=speech,
        llm=model,
        tts=spoken,
        vad=activity,
        turn_handling={"turn_detection": "vad"},
        video_sampler=VoiceActivityVideoSampler(
            speaking_fps=VIDEO_SPEAKING_FPS,
            silent_fps=VIDEO_SILENT_FPS,
        ),
    )
    return VoiceStack(
        session=session,
        provider="livekit",
        realtime_model=model_id,
        voice=CLOUD_VOICE,
        reasoning_effort=effort,
        video_speaking_fps=VIDEO_SPEAKING_FPS,
        video_silent_fps=VIDEO_SILENT_FPS,
        stt=speech,
        llm=model,
        tts=spoken,
    )


def attach_latency_logs(stack: VoiceStack) -> None:
    def on_metrics(metric: AgentMetrics) -> None:
        record = component_latency(metric)
        if record is not None:
            log_json(record)

    # RealtimeModel is not an EventEmitter. Its session forwards metrics here.
    # STT and TTS still emit on their own objects, and the session repeats those,
    # so a realtime stack listens only on the session.
    if hasattr(stack.llm, "on"):
        _listen(stack.stt, on_metrics)
        _listen(stack.llm, on_metrics)
        _listen(stack.tts, on_metrics)
    else:

        def on_session_metrics(ev: MetricsCollectedEvent) -> None:
            on_metrics(ev.metrics)

        stack.session.on("metrics_collected", on_session_metrics)

    def on_item(ev: ConversationItemAddedEvent) -> None:
        if not isinstance(ev.item, ChatMessage):
            return
        record = turn_latency(ev.item.role, ev.item.metrics)
        if record is not None:
            log_json(record)

    stack.session.on("conversation_item_added", on_item)


def _listen(component: object, callback: Callable[[AgentMetrics], None]) -> None:
    on = getattr(component, "on")
    on("metrics_collected", callback)
