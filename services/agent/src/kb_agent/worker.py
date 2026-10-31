import asyncio
import os

import livekit.rtc as rtc
from livekit.agents import AgentServer, JobContext, cli
from qdrant_client import QdrantClient

from kb_agent.latency import log_json
from kb_agent.product import instructions_for, product_id_from_metadata
from kb_agent.support import SupportAgent
from kb_agent.voice import (
    attach_latency_logs,
    build_voice,
    is_screen_share_video,
    session_room_options,
)

AGENT_NAME = "kb-support"
server = AgentServer()


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
    stack = build_voice(livekit_url)
    attach_latency_logs(stack)
    watch_screen_share(ctx.room)
    log_json({"event": "session", "product_id": product_id})
    await stack.session.start(
        agent=SupportAgent(
            instructions=instructions,
            product_id=product_id,
            qdrant=QdrantClient(
                url=os.environ.get("QDRANT_URL") or "http://localhost:6333"
            ),
        ),
        room=ctx.room,
        room_options=session_room_options(),
    )


def main() -> None:
    cli.run_app(server)
