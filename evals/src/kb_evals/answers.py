"""Answer every eval question with Gemini, for `make eval-live` to judge.

The model gets the agent's system prompt and the agent's tools, with search_kb
over the demo index. It answers in text, because the Live model only streams
audio. Cited passages are chosen the way the live agent chooses them.
"""

import argparse
import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from pathlib import Path

from google.genai import Client, types
from kb_agent.prompt import ProductPrompt, render_system_prompt
from kb_agent.retrieve import tool_text
from kb_agent.support import NO_COMPUTER
from kb_rag import Passage, read_directory, supported_ids

from kb_evals.dataset import EvalCase, load_dataset
from kb_evals.run import DATASET_PATH, DOCS_PATH, PRODUCT_ID, RagRetriever

MODEL = "gemini-3.8-flash"
PRODUCT = ProductPrompt(
    name="Northstar Desk",
    description="Northstar Desk is a help-desk product for support teams.",
    tone="calm and brief",
    refusal_rules="Do not invent a policy, a price, or a step.",
)
# A live session opens with the agent's greeting before the user speaks.
# Without it every answer was a first turn and began with an introduction.
GREETING = f"Hi, I'm {PRODUCT.agent_name}. How can I help with {PRODUCT.name}?"
Tool = Callable[..., object]
Generate = Callable[[str, list[types.Content], list[Tool]], Awaitable[str]]


# The prompt names these tools, so the model calls them. An eval row has no
# shared screen, ticket queue, or Mac, so each says what production says then.
def point_at(x: float, y: float, label: str) -> str:
    """Highlight a control on the shared screen.

    Args:
        x: Horizontal position from 0 (left) to 1 (right).
        y: Vertical position from 0 (top) to 1 (bottom).
        label: Short name of the control.
    """
    return "The session preview is not connected, so nothing was shown."


def handoff_to_human(summary: str, reason: str) -> str:
    """Propose a support ticket for a person to pick up.

    Args:
        summary: One sentence naming the customer's problem.
        reason: Why the docs and you could not solve it.
    """
    return (
        "Handoff is not available for this product. "
        "Tell the user you cannot hand this off."
    )


def operate_computer(goal: str) -> str:
    """Do a task on the user's Mac for them, one approved step at a time.

    Args:
        goal: What to get done, in one sentence.
    """
    return NO_COMPUTER


def gemini_generate(model: str) -> Generate:
    client = Client()

    async def generate(
        system: str, contents: list[types.Content], tools: list[Tool]
    ) -> str:
        reply = await client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system, tools=[*tools]
            ),
        )
        return reply.text or ""

    return generate


async def answer(
    case: EvalCase, retriever: RagRetriever, generate: Generate
) -> dict[str, object]:
    seen: dict[str, Passage] = {}

    async def search_kb(query: str) -> str:
        """Search this product's knowledge base.

        Call this before you answer any question about the product.

        Args:
            query: The question to look up, in the user's words.
        """
        found = await retriever.search(query, 5)
        seen.update({p.id: p for p in found.passages})
        return tool_text(found.abstained, found.passages)

    text = await generate(
        render_system_prompt(PRODUCT),
        [
            types.Content(role="model", parts=[types.Part(text=GREETING)]),
            *(
                types.Content(role="user", parts=[types.Part(text=turn)])
                for turn in (*case.turns, case.question)
            ),
        ],
        [search_kb, point_at, handoff_to_human, operate_computer],
    )
    cited = await supported_ids(
        retriever.client, PRODUCT_ID, text, list(seen), settings=retriever.settings
    )
    return {"id": case.id, "answer": text, "cited_passage_ids": cited}


async def write_answers(
    cases: list[EvalCase], retriever: RagRetriever, generate: Generate, out: Path
) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as file:
        for case in cases:
            file.write(json.dumps(await answer(case, retriever, generate)) + "\n")
            file.flush()


async def _run(out: Path, limit: int | None) -> None:
    retriever = RagRetriever()
    await retriever.index(read_directory(DOCS_PATH))
    cases = load_dataset(DATASET_PATH)[:limit]
    await write_answers(cases, retriever, gemini_generate(MODEL), out)
    print(f"wrote {len(cases)} answers to {out}")


def main() -> int:
    parser = argparse.ArgumentParser(prog="kb_evals.answers")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if not os.environ.get("GOOGLE_API_KEY"):
        raise SystemExit("GOOGLE_API_KEY is required")
    asyncio.run(_run(args.out, args.limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
