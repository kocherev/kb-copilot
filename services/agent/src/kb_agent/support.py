from collections.abc import AsyncIterable

from kb_rag import (
    DEFAULT_SETTINGS,
    NOT_IN_DOCS,
    RetrievalSettings,
    SearchResult,
    search,
)
from livekit.agents import (
    Agent,
    ChatContext,
    ChatMessage,
    ModelSettings,
    RunContext,
    function_tool,
    get_job_context,
)
from livekit.agents.llm.tool_context import ToolFlag
from livekit.agents.types import TimedString
from qdrant_client import AsyncQdrantClient, QdrantClient

from kb_agent.hud import point_payload, publish_hud
from kb_agent.latency import log_json
from kb_agent.retrieve import (
    citation_suffix,
    cited_sources,
    retrieval_record,
    tool_text,
)


class SupportAgent(Agent):
    def __init__(
        self,
        *,
        instructions: str,
        product_id: str,
        qdrant: AsyncQdrantClient | QdrantClient,
        settings: RetrievalSettings = DEFAULT_SETTINGS,
    ) -> None:
        self.product_id = product_id
        self.settings = settings
        # The worker still builds a sync client. Search needs the async one.
        self.qdrant = (
            qdrant
            if isinstance(qdrant, AsyncQdrantClient)
            else AsyncQdrantClient(**qdrant.init_options)
        )
        self.sources: list[str] = []
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
        found = await search(
            self.qdrant, self.product_id, query, settings=self.settings
        )
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
        question = new_message.text_content or ""
        found = await search(
            self.qdrant, self.product_id, question, settings=self.settings
        )
        self._remember(found)
        # A greeting also abstains, so the model decides whether to refuse.
        lookup = (
            "No passage matched. If the user asked a product question, say "
            f"exactly: {NOT_IN_DOCS} Otherwise reply briefly without product facts."
            if found.abstained
            else tool_text(found)
        )
        turn_ctx.add_message(
            role="assistant",
            content="Knowledge lookup for the user's latest message:\n" + lookup,
        )

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

    def _remember(self, found: SearchResult) -> None:
        if found.passages:
            self.sources = cited_sources(found)
        log_json(retrieval_record(self.product_id, found))
