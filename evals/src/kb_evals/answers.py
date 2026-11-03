"""Answer every eval question with Gemini, for `make eval-live` to judge.

The model gets the agent's system prompt and the agent's search_kb tool over
the demo index. It answers in text, because the Live model only streams audio.
Cited passages are chosen the way the live agent chooses them.
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
SearchTool = Callable[[str], Awaitable[str]]
Generate = Callable[[str, list[str], SearchTool], Awaitable[str]]


def gemini_generate(model: str) -> Generate:
    client = Client()

    async def generate(system: str, turns: list[str], search_kb: SearchTool) -> str:
        reply = await client.aio.models.generate_content(
            model=model,
            contents=[
                types.Content(role="user", parts=[types.Part(text=t)]) for t in turns
            ],
            config=types.GenerateContentConfig(
                system_instruction=system, tools=[search_kb]
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
        render_system_prompt(PRODUCT), [*case.turns, case.question], search_kb
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
