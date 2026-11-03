import json
import os
from collections.abc import Iterable
from urllib.request import Request, urlopen

from livekit.agents.llm import ChatMessage

from kb_agent.protocol import EscalationProposal

EXCERPT_MESSAGES = 8
EXCERPT_CHARS = 400


def transcript_excerpt(items: Iterable[object]) -> str:
    """The last few spoken lines. The API redacts them before it stores any."""
    lines = [
        f"{'User' if item.role == 'user' else 'Agent'}: {text[:EXCERPT_CHARS]}"
        for item in items
        if isinstance(item, ChatMessage)
        and item.role in ("user", "assistant")
        and (text := " ".join((item.text_content or "").split()))
    ]
    return "\n".join(lines[-EXCERPT_MESSAGES:])


def propose_escalation(
    api_url: str, room: str, summary: str, reason: str, transcript: str
) -> EscalationProposal | None:
    """Ask the API to record a proposed ticket. None when it cannot be offered:
    no Linear connection, no such session, or the API is unreachable."""
    body = json.dumps(
        {"room": room, "summary": summary, "reason": reason, "transcript": transcript}
    ).encode()
    request = Request(
        f"{api_url.rstrip('/')}/internal/escalations",
        data=body,
        headers={
            "content-type": "application/json",
            "X-Internal-Token": os.environ.get("INTERNAL_API_TOKEN", ""),
        },
    )
    try:
        with urlopen(request, timeout=10) as response:
            return EscalationProposal.model_validate_json(response.read())
    except (OSError, ValueError):
        return None
