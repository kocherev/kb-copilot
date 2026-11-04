import asyncio

import httpx
from google.genai import Client
from livekit.agents import Agent, RunContext, function_tool
from livekit.agents.llm.tool_context import ToolFlag

from kb_agent.computer import (
    Approvals,
    ComputerTask,
    Desktop,
    DesktopRoom,
    gemini_planner,
    helper_identity,
)
from kb_agent.handoff import propose_escalation, transcript_excerpt
from kb_agent.knowledge import Knowledge, Passage
from kb_agent.latency import log_json
from kb_agent.protocol import (
    ESCALATION_TOPIC,
    HUD_TOPIC,
    LABEL_LIMIT,
    SNIPPET_LIMIT,
    Citations,
    CitedPassage,
    HudPoint,
    Room,
    publish,
)
from kb_agent.retrieve import retrieval_record, tool_text

NO_COMPUTER = (
    "You cannot act on the user's computer right now: their Mac is not "
    "connected. Offer to guide them step by step with point_at instead. They "
    "can connect their Mac from the session page and ask again."
)


def cited(passage: Passage) -> CitedPassage:
    return CitedPassage(
        id=passage.id,
        title=passage.title,
        source=passage.source,
        anchor=passage.anchor,
        snippet=" ".join(passage.text.split())[:SNIPPET_LIMIT],
    )


class SupportAgent(Agent):
    """The support persona. A new tool is one more @function_tool method here."""

    def __init__(
        self,
        *,
        instructions: str,
        knowledge: Knowledge,
        room: Room,
        api_url: str,
        user: str | None = None,
        agent_name: str = "Shawn",
    ) -> None:
        self.knowledge = knowledge
        self.room = room
        self.api_url = api_url
        # The participant who started the session. Only they approve actions.
        self.user = user
        self.agent_name = agent_name
        # Passages the searches of the current user turn returned, by id.
        self.turn_passages: dict[str, Passage] = {}
        super().__init__(instructions=instructions)

    async def on_enter(self) -> None:
        self.session.generate_reply(
            instructions="Greet the user in one sentence and offer to help."
        )

    @function_tool()
    async def search_kb(self, query: str) -> str:
        """Search this product's knowledge base.

        Call this before you answer any question about the product.

        Args:
            query: The question to look up, in the user's words.
        """
        found = await self.knowledge.search(query)
        self.turn_passages.update({p.id: p for p in found.passages})
        log_json(retrieval_record(self.knowledge.product_id, found))
        return tool_text(found.abstained, found.passages)

    @function_tool()
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

    @function_tool()
    async def handoff_to_human(self, summary: str, reason: str) -> str:
        """Propose a support ticket for a person to pick up.

        Use this only when the docs do not answer the question, or the user asks
        for a person. It shows the ticket on the user's screen. The ticket is
        created only if the user approves it there. You cannot approve it.

        Args:
            summary: One sentence naming the customer's problem.
            reason: Why the docs and you could not solve it.
        """
        proposed = await asyncio.to_thread(
            propose_escalation,
            self.api_url,
            self.room.name,
            summary,
            reason,
            transcript_excerpt(self.chat_ctx.items),
        )
        if proposed is None:
            return (
                "Handoff is not available for this product. "
                "Tell the user you cannot hand this off."
            )
        if not await publish(self.room, ESCALATION_TOPIC, proposed):
            return "The session preview is not connected, so nothing was proposed."
        log_json({"event": "handoff_proposed", "escalation_id": proposed.id})
        return (
            "A ticket is proposed on the user's screen. It exists only if they "
            "approve it there. Ask them to check the card."
        )

    @function_tool(flags=ToolFlag.CANCELLABLE, on_duplicate="reject")
    async def operate_computer(self, ctx: RunContext, goal: str) -> str:
        """Do a task on the user's Mac for them, one approved step at a time.

        Call this only after you said what you will do and the user said yes.
        Each step appears on the user's screen and runs only when they allow
        it there. You cannot allow a step yourself.

        Args:
            goal: What to get done, in one sentence, such as "Open Billing and
                click Update card".
        """
        room = self.room
        helper = helper_identity(self.user) if self.user else None
        if (
            self.user is None
            or helper is None
            or not isinstance(room, DesktopRoom)
            or helper not in room.remote_participants
        ):
            return NO_COMPUTER
        try:
            found = await self.knowledge.search(goal)
            passages = () if found.abstained else found.passages
        except httpx.HTTPError:
            passages = ()
        await ctx.update(
            "Starting. Each step waits until the user allows it on their screen."
        )
        task = ComputerTask(
            room=room,
            desktop=Desktop(room, helper),
            approvals=Approvals(self.user),
            plan=gemini_planner(Client()),
            api=self.knowledge.client,
            say=ctx.update,
            agent_name=self.agent_name,
        )
        return await task.run(goal, passages)

    def new_user_turn(self) -> None:
        self.turn_passages = {}

    async def citations_for(self, message_id: str, text: str) -> Citations | None:
        """The passages of this turn that support an assistant message, if any."""
        if not self.turn_passages:
            return None
        ids = await self.knowledge.supported(text, list(self.turn_passages))
        if not ids:
            return None
        return Citations(
            message_id=message_id,
            text=text,
            passages=[cited(self.turn_passages[i]) for i in ids],
        )
