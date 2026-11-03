"""What the agent and the web page send each other over the room data channel.

The names here are mirrored in apps/web/src/lib/protocol.ts.
tests/test_protocol.py fails when the two files drift.
"""

import json
from typing import Literal, Protocol

from pydantic import BaseModel, Field

AGENT_NAME = "kb-support"
HUD_TOPIC = "hud"
CITATIONS_TOPIC = "citations"
AGENT_ERROR_TOPIC = "agent-error"
ESCALATION_TOPIC = "escalation"
COMPUTER_TOPIC = "computer"
COMPUTER_DECISION_TOPIC = "computer-decision"

LABEL_LIMIT = 80
SNIPPET_LIMIT = 280


class HudPoint(BaseModel):
    """A highlight on the shared frame. x and y are fractions from the top left.

    clicking means the agent is clicking there on the user's computer now."""

    kind: Literal["point", "clicking"] = "point"
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    label: str = Field(min_length=1, max_length=LABEL_LIMIT)


class CitedPassage(BaseModel):
    id: str
    title: str
    source: str
    anchor: str
    snippet: str = Field(max_length=SNIPPET_LIMIT)


class Citations(BaseModel):
    """The passages that support one assistant message.

    The web page joins this to a transcript line by text, because the
    transcript stream ids are not the message id.
    """

    message_id: str
    text: str
    passages: list[CitedPassage]


class AgentError(BaseModel):
    message: str


class EscalationProposal(BaseModel):
    """A ticket the agent proposes. Nothing is sent to Linear until the user approves.

    The text is what the API stored, already redacted.
    """

    id: str
    title: str
    body: str


class ActionProposal(BaseModel):
    """One step of a computer task, shown in the approval tray.

    x and y are fractions of the screen for a step that points somewhere.
    needs_approval is false while the user has allowed the rest of the task,
    and the tray then only offers to stop. warning is the model's safety
    explanation when it asks for an explicit confirmation."""

    kind: Literal["proposal"] = "proposal"
    id: str
    task: str
    description: str = Field(min_length=1, max_length=200)
    x: float | None = Field(default=None, ge=0, le=1)
    y: float | None = Field(default=None, ge=0, le=1)
    needs_approval: bool
    warning: str = ""


class TaskEnded(BaseModel):
    kind: Literal["ended"] = "ended"
    task: str
    reason: str


class Decision(BaseModel):
    """The user's answer to a proposal. Sent by the page, never by the agent."""

    id: str
    decision: Literal["once", "task", "stop"]


class Publisher(Protocol):
    async def publish_data(
        self, payload: bytes, *, reliable: bool = True, topic: str = ""
    ) -> None: ...


class Room(Protocol):
    @property
    def name(self) -> str: ...

    def isconnected(self) -> bool: ...

    @property
    def local_participant(self) -> Publisher: ...


async def publish(room: Room, topic: str, message: BaseModel) -> bool:
    """Send one message. False when the room is gone, so callers can move on."""
    if not room.isconnected():
        return False
    body = json.dumps(message.model_dump(), sort_keys=True).encode()
    await room.local_participant.publish_data(body, reliable=True, topic=topic)
    return True
