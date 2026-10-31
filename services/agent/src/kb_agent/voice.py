from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlparse

import livekit.rtc as rtc
from livekit.agents import (
    AgentSession,
    ConversationItemAddedEvent,
    inference,
    llm,
    room_io,
    stt,
    tts,
)
from livekit.agents.llm import ChatMessage
from livekit.agents.metrics import AgentMetrics

from kb_agent.latency import component_latency, log_json, turn_latency

CLOUD_STT = "assemblyai/universal-3-6-pro"
CLOUD_LLM = "google/gemma-4-31b-it"
CLOUD_TTS = "fishaudio/s2.1-pro"
CLOUD_TTS_VOICE = "fa4c9eb3dccc4806b382b40d61c6b10a"
OPENAI_STT = "gpt-4o-mini-transcribe"
OPENAI_LLM = "gpt-4.1-mini"
OPENAI_TTS = "gpt-4o-mini-tts"
OPENAI_VOICE = "ash"


def model_provider(livekit_url: str) -> str:
    host = (urlparse(livekit_url).hostname or "").lower().rstrip(".")
    if host == "livekit.cloud" or host.endswith(".livekit.cloud"):
        return "livekit"
    return "openai"


def session_room_options() -> room_io.RoomOptions:
    # RoomIO subscribes to screen-share video only when video input is enabled.
    return room_io.RoomOptions(video_input=True)


def is_screen_share_video(source: int, kind: int) -> bool:
    screen = source == rtc.TrackSource.SOURCE_SCREENSHARE
    video = kind == rtc.TrackKind.KIND_VIDEO
    return screen and video


@dataclass
class VoiceStack:
    session: AgentSession
    stt: stt.STT
    llm: llm.LLM
    tts: tts.TTS


def build_voice(livekit_url: str) -> VoiceStack:
    if model_provider(livekit_url) == "livekit":
        speech = inference.STT(model=CLOUD_STT, language="en")
        model = inference.LLM(model=CLOUD_LLM)
        voice = inference.TTS(model=CLOUD_TTS, voice=CLOUD_TTS_VOICE)
        return VoiceStack(
            session=AgentSession(stt=speech, llm=model, tts=voice),
            stt=speech,
            llm=model,
            tts=voice,
        )
    from livekit.plugins import openai

    speech = openai.STT(model=OPENAI_STT)
    model = openai.responses.LLM(model=OPENAI_LLM)
    voice = openai.TTS(model=OPENAI_TTS, voice=OPENAI_VOICE)
    return VoiceStack(
        session=AgentSession(stt=speech, llm=model, tts=voice),
        stt=speech,
        llm=model,
        tts=voice,
    )


def attach_latency_logs(stack: VoiceStack) -> None:
    def on_metrics(metric: AgentMetrics) -> None:
        record = component_latency(metric)
        if record is not None:
            log_json(record)

    _listen(stack.stt, on_metrics)
    _listen(stack.llm, on_metrics)
    _listen(stack.tts, on_metrics)

    def on_item(ev: ConversationItemAddedEvent) -> None:
        if not isinstance(ev.item, ChatMessage):
            return
        record = turn_latency(ev.item.role, ev.item.metrics)
        if record is not None:
            log_json(record)

    stack.session.on("conversation_item_added", on_item)


def _listen(
    component: stt.STT | llm.LLM | tts.TTS,
    callback: Callable[[AgentMetrics], None],
) -> None:
    component.on("metrics_collected", callback)
