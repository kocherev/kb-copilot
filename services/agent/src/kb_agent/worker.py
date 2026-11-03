import asyncio
import contextlib
import os
from collections.abc import Callable, Coroutine

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

from kb_agent.config import require_settings
from kb_agent.knowledge import api_client
from kb_agent.latency import log_json
from kb_agent.product import (
    fetch_product,
    product_id_from_metadata,
    user_from_metadata,
)
from kb_agent.prompt import render_system_prompt
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
from kb_agent.turns import LoggedKnowledge, TurnLog

LISTENER_WAIT_SECONDS = 30
# LiveKit keeps one warm job process per CPU by default, 8 in the Docker VM.
# Each one holds the livekit and Gemini libraries, about 1.1 GiB together while
# no session runs. One warm process starts the next session at once.
server = AgentServer(num_idle_processes=1)
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
    session: AgentSession, agent: SupportAgent, room: rtc.Room, turns: TurnLog
) -> None:
    async def cite(message: ChatMessage) -> None:
        found = None
        try:
            found = await agent.citations_for(message.id, message.text_content or "")
            if found is not None:
                await publish(room, CITATIONS_TOPIC, found)
        except Exception as exc:
            log_json({"event": "citations_failed", "error": type(exc).__name__})
        turns.assistant(message, [p.id for p in found.passages] if found else [])

    @session.on("conversation_item_added")
    def on_item(ev: ConversationItemAddedEvent) -> None:
        if not isinstance(ev.item, ChatMessage):
            return
        if ev.item.role == "user":
            agent.new_user_turn()
            turns.user(ev.item)
        elif ev.item.role == "assistant":
            spawn(cite(ev.item))


def enable_tracing(
    room: str, product_id: str
) -> Callable[[], Coroutine[None, None, None]] | None:
    """Export LiveKit's session traces over OTLP. Returns the flush to run at the end.

    Off unless OTEL_EXPORTER_OTLP_ENDPOINT is set, and then nothing loads.
    """
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return None
    from livekit.agents.telemetry import set_tracer_provider
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    # The conversation stays in the replay, where it is redacted.
    set_tracer_provider(
        provider,
        metadata={"kb.room": room, "kb.product_id": product_id},
        allow_pii=False,
    )

    async def flush() -> None:
        await asyncio.to_thread(provider.force_flush)

    return flush


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()
    api_url = os.environ.get("API_URL", "http://localhost:8000")
    limit: asyncio.Task[None] | None = None
    try:
        product_id = product_id_from_metadata(ctx.job.metadata)
        user = user_from_metadata(ctx.job.metadata)
        token = os.environ.get("INTERNAL_API_TOKEN", "")
        turns = TurnLog(ctx.room.name, api_client(api_url, token))
        knowledge = LoggedKnowledge(product_id, api_client(api_url, token), turns)
        ctx.add_shutdown_callback(knowledge.aclose)
        ctx.add_shutdown_callback(turns.flush)
        flush_traces = enable_tracing(ctx.room.name, product_id)
        if flush_traces is not None:
            ctx.add_shutdown_callback(flush_traces)
        product = await asyncio.to_thread(fetch_product, api_url, product_id)
        session = build_session(product.voice)
        agent = SupportAgent(
            instructions=render_system_prompt(product),
            knowledge=knowledge,
            room=ctx.room,
            api_url=api_url,
            user=user,
            agent_name=product.agent_name,
        )
        attach_logs(session, turns)
        publish_citations(session, agent, ctx.room, turns)

        async def closed(ev: CloseEvent) -> None:
            if ev.reason == CloseReason.ERROR:
                await report_failure(
                    ctx.room, ev.error.error if ev.error else RuntimeError("closed")
                )
            ctx.shutdown(reason=ev.reason.value)

        session.on("close", lambda ev: spawn(closed(ev)))
        log_json({"event": "session", "product_id": product_id})
        await session.start(agent=agent, room=ctx.room, room_options=room_options(user))
        limit = asyncio.create_task(
            enforce_time_limit(
                session,
                max_session_seconds(os.environ.get("AGENT_MAX_SESSION_SECONDS")),
                lambda: session.shutdown(),
            )
        )
    except Exception as exc:
        await report_failure(ctx.room, exc)
        ctx.shutdown(reason="agent error")
        return

    async def cleanup() -> None:
        if limit is not None:
            limit.cancel()

    ctx.add_shutdown_callback(cleanup)


def main() -> None:
    require_settings(os.environ)
    cli.run_app(server)
