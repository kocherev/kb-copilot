"""Prove vision and tools against the live model with one command.

    GOOGLE_API_KEY=... uv run python -m kb_agent.selfcheck \
        --image services/agent/tests/fixtures/billing-screen.png \
        --question "What does the red banner say, and which button fixes it?"

It runs the production session, prompt and tools headless, streams the image
as the shared screen, asks the question as text, and prints the reply, the
tools called and the token usage. It exits 1 when the model was billed no
image tokens, because then it never saw the picture.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

import httpx
from kb_rag import DEFAULT_SETTINGS, index_sources, read_directory
from livekit import rtc
from livekit.agents import CloseEvent, MetricsCollectedEvent
from livekit.agents.metrics import RealtimeModelMetrics
from livekit.agents.voice.io import VideoInput
from livekit.agents.voice.run_result import ChatMessageEvent, FunctionCallEvent
from PIL import Image
from qdrant_client import AsyncQdrantClient

from kb_agent.config import missing_settings
from kb_agent.knowledge import Knowledge
from kb_agent.latency import log_json
from kb_agent.local_api import local_api
from kb_agent.prompt import ProductPrompt, render_system_prompt
from kb_agent.session import ScreenSampler, build_session
from kb_agent.support import SupportAgent

PRODUCT_ID = "selfcheck"
PRODUCT = ProductPrompt(
    name="Northstar Desk",
    description="Northstar Desk is a help desk for support teams.",
    tone="calm and brief",
    refusal_rules="Do not invent a policy.",
)
TIMEOUT_SECONDS = 120


def load_frame(path: Path) -> rtc.VideoFrame:
    picture = Image.open(path).convert("RGBA")
    return rtc.VideoFrame(
        picture.width, picture.height, rtc.VideoBufferType.RGBA, picture.tobytes()
    )


class SharedScreen(VideoInput):
    """The same picture, again every second, like a screen that stays put."""

    def __init__(self, frame: rtc.VideoFrame) -> None:
        super().__init__(label="selfcheck")
        self._frame = frame
        self._first = True

    async def __anext__(self) -> rtc.VideoFrame:
        if not self._first:
            await asyncio.sleep(1)
        self._first = False
        return self._frame


class PrintRoom:
    """Stands in for the room: highlights are printed instead of drawn."""

    name = "selfcheck"

    @property
    def local_participant(self) -> "PrintRoom":
        return self

    def isconnected(self) -> bool:
        return True

    async def publish_data(
        self, payload: bytes, *, reliable: bool = True, topic: str = ""
    ) -> None:
        print(f"  [{topic}] {payload.decode()}")


async def check(image: Path, question: str, docs: Path) -> int:
    client = AsyncQdrantClient(":memory:")
    await index_sources(client, PRODUCT_ID, read_directory(docs))
    session = build_session(PRODUCT.voice, ScreenSampler())
    session.input.video = SharedScreen(load_frame(image))
    agent = SupportAgent(
        instructions=render_system_prompt(PRODUCT),
        knowledge=Knowledge(
            PRODUCT_ID,
            httpx.AsyncClient(
                transport=local_api(client, DEFAULT_SETTINGS),
                base_url="http://api.local",
            ),
        ),
        room=PrintRoom(),
        api_url=os.environ.get("API_URL", "http://localhost:8000"),
    )
    usage: list[RealtimeModelMetrics] = []

    @session.on("metrics_collected")
    def on_metrics(ev: MetricsCollectedEvent) -> None:
        if isinstance(ev.metrics, RealtimeModelMetrics):
            usage.append(ev.metrics)

    failures: list[str] = []

    @session.on("close")
    def on_close(ev: CloseEvent) -> None:
        if ev.error is not None:
            failures.append(str(ev.error.error))

    await session.start(agent=agent, record=False)
    try:
        result = await asyncio.wait_for(
            session.run(user_input=question), TIMEOUT_SECONDS
        )
    finally:
        await session.aclose()

    tools = [e.item.name for e in result.events if isinstance(e, FunctionCallEvent)]
    reply = " ".join(
        e.item.text_content or ""
        for e in result.events
        if isinstance(e, ChatMessageEvent)
    ).strip()
    image_tokens = sum(u.input_token_details.image_tokens for u in usage)
    print(f"reply: {reply}")
    print(f"tools called: {', '.join(tools) or 'none'}")
    print(
        f"usage: input {sum(u.input_tokens for u in usage)}, "
        f"output {sum(u.output_tokens for u in usage)}, image {image_tokens}"
    )
    if failures:
        print(f"FAIL: the session closed with an error: {failures[0]}")
        return 1
    if image_tokens == 0:
        print("FAIL: no image tokens were billed, so the model did not see the screen.")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kb_agent.selfcheck")
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--docs", type=Path, default=Path("demo/docs/billing"))
    args = parser.parse_args(argv)
    if missing_settings(os.environ, ("GOOGLE_API_KEY",)):
        print("skipped: GOOGLE_API_KEY is not set")
        return 0
    log_json({"event": "selfcheck", "image": args.image.name})
    return asyncio.run(check(args.image, args.question, args.docs))


if __name__ == "__main__":
    sys.exit(main())
