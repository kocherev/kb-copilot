import asyncio
from collections.abc import AsyncIterable

from livekit.agents import (
    Agent,
    ChatContext,
    ChatMessage,
    ModelSettings,
    RunContext,
    StopResponse,
    function_tool,
    get_job_context,
    llm,
)
from livekit.agents.llm.tool_context import ToolFlag
from livekit.agents.types import FlushSentinel, TimedString
from qdrant_client import QdrantClient

from kb_agent.hud import point_payload, publish_hud
from kb_agent.latency import log_json
from kb_agent.retrieve import (
    NOT_IN_DOCS,
    KbSearch,
    citation_suffix,
    content_tokens,
    retrieval_record,
    tool_text,
)
from kb_agent.retrieve import search_kb as lookup_kb


class SupportAgent(Agent):
    def __init__(
        self,
        *,
        instructions: str,
        product_id: str,
        qdrant: QdrantClient,
    ) -> None:
        self.product_id = product_id
        self.qdrant = qdrant
        self.sources: list[str] = []
        self._refuse = False
        super().__init__(instructions=instructions)

    async def on_enter(self) -> None:
        self.session.generate_reply(
            instructions="Greet the user in one sentence and offer to help."
        )

    @function_tool(flags=ToolFlag.IGNORE_ON_ENTER)
    async def search_kb(self, context: RunContext, query: str) -> str:
        """Search this product's knowledge base.

        Call this when the lookup already in the conversation is not enough.
        If the result says the answer is not in the docs, do not invent one.

        Args:
            query: The question to look up, using the user's words.
        """
        del context
        found = await asyncio.to_thread(lookup_kb, self.qdrant, self.product_id, query)
        self._remember(found)
        return tool_text(found)

    @function_tool(flags=ToolFlag.IGNORE_ON_ENTER)
    async def point_at(
        self,
        context: RunContext,
        x: float,
        y: float,
        label: str,
    ) -> str:
        """Highlight a control on the shared screen.

        x and y are fractions from 0 to 1, measured from the top left of the
        picture you see. This draws a highlight on the session preview. It does
        not move the mouse or click.

        Args:
            x: Horizontal position. 0 is the left edge and 1 is the right edge.
            y: Vertical position. 0 is the top edge and 1 is the bottom edge.
            label: Short name of the control, such as Review status.
        """
        del context
        payload = point_payload(x, y, label)
        await publish_hud(get_job_context().room, payload)
        return (
            "Highlight shown on the session preview. "
            "The user still clicks. You did not move the mouse."
        )

    async def on_user_turn_completed(
        self,
        turn_ctx: ChatContext,
        new_message: ChatMessage,
    ) -> None:
        self.sources = []
        self._refuse = False
        question = new_message.text_content or ""
        if not content_tokens(question):
            return
        found = await asyncio.to_thread(
            lookup_kb, self.qdrant, self.product_id, question
        )
        self._remember(found)
        if not found.hits:
            self._refuse = True
            if isinstance(self.llm, llm.RealtimeModel):
                # Realtime audio does not pass through llm_node. Speak the
                # exact refusal with TTS, then skip the model reply.
                self.session.say(NOT_IN_DOCS)
                raise StopResponse()
            return
        turn_ctx.add_message(
            role="assistant",
            content="Knowledge lookup for the user's latest message:\n"
            + tool_text(found),
        )

    async def llm_node(
        self,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool],
        model_settings: ModelSettings,
    ) -> AsyncIterable[llm.ChatChunk | str | FlushSentinel]:
        if self._refuse:
            yield NOT_IN_DOCS
            return
        async for chunk in Agent.default.llm_node(
            self, chat_ctx, tools, model_settings
        ):
            yield chunk

    async def transcription_node(
        self,
        text: AsyncIterable[str | TimedString],
        model_settings: ModelSettings,
    ) -> AsyncIterable[str | TimedString]:
        del model_settings
        async for delta in text:
            yield delta
        suffix = citation_suffix(self.sources)
        if suffix:
            yield suffix

    def _remember(self, found: KbSearch) -> None:
        if found.hits:
            self.sources = found.source_urls()
        log_json(retrieval_record(self.product_id, found))
