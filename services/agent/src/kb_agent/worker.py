import asyncio
import os

import livekit.rtc as rtc
from livekit.agents import AgentServer, JobContext, cli
from qdrant_client import QdrantClient

from kb_agent.hud import bind_screen_hud
from kb_agent.latency import log_json
from kb_agent.product import instructions_for, product_id_from_metadata
from kb_agent.support import SupportAgent
from kb_agent.voice import (
    attach_latency_logs,
    build_voice,
    is_screen_share_video,
    session_room_options,
    voice_attempts,
)

AGENT_NAME = "kb-support"
server = AgentServer()


def _prewarm(proc: object) -> None:
    # The realtime session module is heavy. Load it before the job loop starts.
    del proc
    from livekit.agents import inference

    if inference.RealtimeModel is None:
        raise RuntimeError("realtime model failed to load")


server.setup_fnc = _prewarm


def watch_screen_share(room: rtc.Room) -> None:
    @room.on("track_subscribed")
    def on_subscribed(
        _track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        _participant: rtc.RemoteParticipant,
    ) -> None:
        if is_screen_share_video(publication.source, publication.kind):
            log_json({"event": "screen_share", "subscribed": True})


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: JobContext) -> None:
    product_id = product_id_from_metadata(ctx.job.metadata)
    api_url = os.environ.get("API_URL", "http://localhost:8000")
    instructions = await asyncio.to_thread(instructions_for, ctx.job.metadata, api_url)
    livekit_url = os.environ.get("LIVEKIT_URL", "")
    watch_screen_share(ctx.room)
    log_json({"event": "session", "product_id": product_id})
    qdrant = QdrantClient(
        url=os.environ.get("QDRANT_URL") or "http://localhost:6333",
        api_key=os.environ.get("QDRANT_API_KEY") or None,
    )
    last_error: Exception | None = None
    for model_id in voice_attempts(livekit_url):
        stack = build_voice(livekit_url, realtime_model=model_id)
        attach_latency_logs(stack)
        bind_screen_hud(stack.session, ctx.room)
        try:
            await stack.session.start(
                agent=SupportAgent(
                    instructions=instructions,
                    product_id=product_id,
                    qdrant=qdrant,
                ),
                room=ctx.room,
                room_options=session_room_options(),
            )
        except Exception as exc:
            last_error = exc
            log_json(
                {
                    "error": type(exc).__name__,
                    "event": "voice_fallback",
                    "model": stack.realtime_model or "openai",
                }
            )
            await stack.session.aclose()
            continue
        log_json(
            {
                "event": "voice",
                "model": stack.realtime_model or "openai",
                "provider": stack.provider,
                "reasoning_effort": stack.reasoning_effort,
            }
        )
        return
    if last_error is not None:
        raise last_error


def main() -> None:
    cli.run_app(server)
