import asyncio

from kb_rag import DEFAULT_SETTINGS, Passage, RetrievalSettings, search
from livekit.agents import Agent, function_tool
from livekit.agents.llm.tool_context import ToolFlag
from qdrant_client import AsyncQdrantClient

from kb_agent.citations import cited, supporting_passages
from kb_agent.latency import log_json
from kb_agent.protocol import (
    HUD_TOPIC,
    LABEL_LIMIT,
    Citations,
    HudPoint,
    Room,
    publish,
)
from kb_agent.retrieve import retrieval_record, tool_text


class SupportAgent(Agent):
    """The support persona. A new tool is one more @function_tool method here."""

    def __init__(
        self,
        *,
        instructions: str,
        product_id: str,
        qdrant: AsyncQdrantClient,
        room: Room,
        settings: RetrievalSettings = DEFAULT_SETTINGS,
    ) -> None:
        self.product_id = product_id
        self.qdrant = qdrant
        self.room = room
        self.settings = settings
        # Passages the searches of the current user turn returned, by id.
        self.turn_passages: dict[str, Passage] = {}
        super().__init__(instructions=instructions)

    async def on_enter(self) -> None:
        self.session.generate_reply(
            instructions="Greet the user in one sentence and offer to help."
        )

    @function_tool(flags=ToolFlag.IGNORE_ON_ENTER)
    async def search_kb(self, query: str) -> str:
        """Search this product's knowledge base.

        Call this before you answer any question about the product.

        Args:
            query: The question to look up, in the user's words.
        """
        found = await search(
            self.qdrant, self.product_id, query, settings=self.settings
        )
        self.turn_passages.update({p.id: p for p in found.passages})
        log_json(retrieval_record(self.product_id, found))
        return tool_text(found)

    @function_tool(flags=ToolFlag.IGNORE_ON_ENTER)
    async def point_at(self, x: float, y: float, label: str) -> str:
        """Highlight a control on the shared screen.

        x and y are fractions from 0 to 1, measured from the top left of the
        picture you see. This draws a highlight on the session preview. It does
        not move the mouse or click.

        Args:
            x: Horizontal position. 0 is the left edge and 1 is the right edge.
            y: Vertical position. 0 is the top edge and 1 is the bottom edge.
            label: Short name of the control, such as Review status.
        """
        point = HudPoint(
            x=min(max(x, 0), 1),
            y=min(max(y, 0), 1),
            label=" ".join(label.split())[:LABEL_LIMIT] or "Here",
        )
        if not await publish(self.room, HUD_TOPIC, point):
            return "The session preview is not connected, so nothing was shown."
        return (
            "Highlight shown on the session preview. "
            "The user still clicks. You did not move the mouse."
        )

    def new_user_turn(self) -> None:
        self.turn_passages = {}

    async def citations_for(self, message_id: str, text: str) -> Citations | None:
        """The passages of this turn that support an assistant message, if any."""
        supported = await asyncio.to_thread(
            supporting_passages,
            text,
            list(self.turn_passages.values()),
            self.settings.dense,
        )
        if not supported:
            return None
        return Citations(
            message_id=message_id, text=text, passages=[cited(p) for p in supported]
        )
