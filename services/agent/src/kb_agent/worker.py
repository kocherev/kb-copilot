import asyncio
import contextlib
import os
from collections.abc import Coroutine

from livekit import rtc
from livekit.agents import (
    AgentServer,
    AgentSession,
    CloseEvent,
    ConversationItemAddedEvent,
    JobContext,
    cli,
)
from livekit.agents.llm import ChatMessage
from livekit.agents.voice.events import CloseReason
from qdrant_client import AsyncQdrantClient

from kb_agent.config import require_settings
from kb_agent.latency import log_json
from kb_agent.product import instructions_for, product_id_from_metadata
from kb_agent.protocol import (
    AGENT_ERROR_TOPIC,
    AGENT_NAME,
    CITATIONS_TOPIC,
    AgentError,
    publish,
)
from kb_agent.session import (
    attach_logs,
    build_session,
    enforce_time_limit,
    max_session_seconds,
    room_options,
)
from kb_agent.support import SupportAgent

LISTENER_WAIT_SECONDS = 30
server = AgentServer()
# The loop keeps only weak references to tasks, so hold them until they finish.
_running: set[asyncio.Task[None]] = set()


def spawn(work: Coroutine[None, None, None]) -> None:
    task = asyncio.get_running_loop().create_task(work)
    _running.add(task)
    task.add_done_callback(_running.discard)


async def wait_for_listener(room: rtc.Room) -> None:
    """A message sent before anyone joined would reach nobody."""
    if room.remote_participants:
        return
    joined = asyncio.Event()
    room.once("participant_connected", lambda _participant: joined.set())
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(joined.wait(), LISTENER_WAIT_SECONDS)


async def report_failure(room: rtc.Room, exc: Exception) -> None:
    """Tell the page why the agent will not speak, so the room is never just silent."""
    log_json({"event": "agent_error", "error": type(exc).__name__})
    await wait_for_listener(room)
    message = (
        f"The agent could not start ({type(exc).__name__}). "
        "Try again in a moment. If it keeps failing, check the agent logs."
    )
    with contextlib.suppress(Exception):
        await publish(room, AGENT_ERROR_TOPIC, AgentError(message=message))


def publish_citations(
    session: AgentSession, agent: SupportAgent, room: rtc.Room
) -> None:
    async def cite(message: ChatMessage) -> None:
        try:
            found = await agent.citations_for(message.id, message.text_content or "")
            if found is not None:
                await publish(room, CITATIONS_TOPIC, found)
        except Exception as exc:
            log_json({"event": "citations_failed", "error": type(exc).__name__})

    @session.on("conversation_item_added")
    def on_item(ev: ConversationItemAddedEvent) -> None:
        if not isinstance(ev.item, ChatMessage):
            return
        if ev.item.role == "user":
            agent.new_user_turn()
        elif ev.item.role == "assistant":
            spawn(cite(ev.item))


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()
    qdrant = AsyncQdrantClient(
        url=os.environ.get("QDRANT_URL") or "http://localhost:6333",
        api_key=os.environ.get("QDRANT_API_KEY") or None,
    )
    limit: asyncio.Task[None] | None = None
    try:
        product_id = product_id_from_metadata(ctx.job.metadata)
        api_url = os.environ.get("API_URL", "http://localhost:8000")
        instructions = await asyncio.to_thread(
            instructions_for, ctx.job.metadata, api_url
        )
        session = build_session()
        agent = SupportAgent(
            instructions=instructions,
            product_id=product_id,
            qdrant=qdrant,
            room=ctx.room,
            api_url=api_url,
        )
        attach_logs(session)
        publish_citations(session, agent, ctx.room)

        async def closed(ev: CloseEvent) -> None:
            if ev.reason == CloseReason.ERROR:
                await report_failure(
                    ctx.room, ev.error.error if ev.error else RuntimeError("closed")
                )
            ctx.shutdown(reason=ev.reason.value)

        session.on("close", lambda ev: spawn(closed(ev)))
        log_json({"event": "session", "product_id": product_id})
        await session.start(agent=agent, room=ctx.room, room_options=room_options())
        limit = asyncio.create_task(
            enforce_time_limit(
                session,
                max_session_seconds(os.environ.get("AGENT_MAX_SESSION_SECONDS")),
                lambda: session.shutdown(),
            )
        )
    except Exception as exc:
        await report_failure(ctx.room, exc)
        await qdrant.close()
        ctx.shutdown(reason="agent error")
        return

    async def cleanup() -> None:
        if limit is not None:
            limit.cancel()
        await qdrant.close()

    ctx.add_shutdown_callback(cleanup)


def main() -> None:
    require_settings(os.environ)
    cli.run_app(server)
