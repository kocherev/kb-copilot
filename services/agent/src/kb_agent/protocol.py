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

LABEL_LIMIT = 80
SNIPPET_LIMIT = 280


class HudPoint(BaseModel):
    """A highlight on the shared frame. x and y are fractions from the top left."""

    kind: Literal["point"] = "point"
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


class Publisher(Protocol):
    async def publish_data(
        self, payload: bytes, *, reliable: bool = True, topic: str = ""
    ) -> None: ...


class Room(Protocol):
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
