import asyncio
from collections.abc import AsyncIterable

from livekit.agents import (
    Agent,
    ChatContext,
    ChatMessage,
    ModelSettings,
    RunContext,
    function_tool,
    llm,
)
from livekit.agents.llm.tool_context import ToolFlag
from livekit.agents.types import FlushSentinel, TimedString
from qdrant_client import QdrantClient

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
