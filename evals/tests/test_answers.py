import asyncio
import json
from pathlib import Path

from google.genai import types
from kb_agent.support import NO_COMPUTER, SupportAgent
from kb_evals.answers import Tool, write_answers
from kb_evals.dataset import EvalCase
from kb_evals.run import RagRetriever
from kb_rag import Source
from kb_rag.testing import HASH_SETTINGS
from livekit.agents.llm import find_function_tools

REFUNDS = Source(
    source="refunds.md",
    text="Refunds take five business days to reach your card.",
    markdown=False,
)


async def _call(tools: list[Tool], name: str, **args: object) -> str:
    """Dispatch by name, as the Gemini SDK does with automatic function calls."""
    result = {tool.__name__: tool for tool in tools}[name](**args)
    return str(await result if asyncio.iscoroutine(result) else result)


def _case(case_id: str, question: str, turns: tuple[str, ...] = ()) -> EvalCase:
    return EvalCase(
        id=case_id,
        category="answerable",
        question=question,
        gold_answer="x",
        required_facts=(),
        expected_sources=(),
        turns=turns,
    )


def test_answers_are_written_in_the_judge_format_with_cited_passage_ids(
    tmp_path: Path,
) -> None:
    prompts: list[tuple[str, list[types.Content]]] = []

    async def generate(
        system: str, contents: list[types.Content], tools: list[Tool]
    ) -> str:
        prompts.append((system, contents))
        found = await _call(tools, "search_kb", query="refunds take five business days")
        assert "abstained: false" in found
        return "Refunds take five business days to reach your card."

    async def run() -> None:
        retriever = RagRetriever(HASH_SETTINGS)
        await retriever.index([REFUNDS])
        await write_answers(
            [_case("c1", "How long do refunds take?", ("Hi",))],
            retriever,
            generate,
            tmp_path / "runs" / "answers.jsonl",
        )

    asyncio.run(run())

    [line] = (tmp_path / "runs" / "answers.jsonl").read_text().splitlines()
    row = json.loads(line)
    assert set(row) == {"id", "answer", "cited_passage_ids"}
    assert row["id"] == "c1"
    assert len(row["cited_passage_ids"]) == 1
    system, contents = prompts[0]
    assert "Call search_kb before you answer" in system
    assert [(c.role, (c.parts or [])[0].text) for c in contents] == [
        ("model", "Hi, I'm Shawn. How can I help with Northstar Desk?"),
        ("user", "Hi"),
        ("user", "How long do refunds take?"),
    ]


def test_a_refusal_cites_nothing(tmp_path: Path) -> None:
    async def generate(
        system: str, contents: list[types.Content], tools: list[Tool]
    ) -> str:
        await _call(tools, "search_kb", query="zebras gallop northward")
        return "That is not in the docs."

    async def run() -> None:
        retriever = RagRetriever(HASH_SETTINGS)
        await retriever.index([REFUNDS])
        await write_answers(
            [_case("c2", "Zebras?")], retriever, generate, tmp_path / "a.jsonl"
        )

    asyncio.run(run())

    row = json.loads((tmp_path / "a.jsonl").read_text())
    assert row["answer"] == "That is not in the docs."
    assert row["cited_passage_ids"] == []


def test_every_agent_tool_answers_as_production_does_without_a_session(
    tmp_path: Path,
) -> None:
    replies: dict[str, str] = {}
    args = {
        "search_kb": {"query": "refunds"},
        "point_at": {"x": 0.5, "y": 0.5, "label": "Billing"},
        "handoff_to_human": {"summary": "Refund", "reason": "Not in the docs"},
        "operate_computer": {"goal": "Open Billing"},
    }

    async def generate(
        system: str, contents: list[types.Content], tools: list[Tool]
    ) -> str:
        for tool in find_function_tools(SupportAgent):
            name = tool.id
            replies[name] = await _call(tools, name, **args[name])
        return "That is not in the docs."

    async def run() -> None:
        retriever = RagRetriever(HASH_SETTINGS)
        await retriever.index([REFUNDS])
        await write_answers(
            [_case("c3", "Hand me to a person")], retriever, generate, tmp_path / "a"
        )

    asyncio.run(run())

    assert set(replies) == set(args)
    assert replies["point_at"].startswith("The session preview is not connected")
    assert replies["handoff_to_human"].startswith("Handoff is not available")
    assert replies["operate_computer"] == NO_COMPUTER
