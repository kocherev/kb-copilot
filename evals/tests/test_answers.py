import asyncio
import json
from pathlib import Path

from kb_evals.answers import SearchTool, write_answers
from kb_evals.dataset import EvalCase
from kb_evals.run import RagRetriever
from kb_rag import Source
from kb_rag.testing import HASH_SETTINGS

REFUNDS = Source(
    source="refunds.md",
    text="Refunds take five business days to reach your card.",
    markdown=False,
)


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
    prompts: list[tuple[str, list[str]]] = []

    async def generate(system: str, turns: list[str], search_kb: SearchTool) -> str:
        prompts.append((system, turns))
        found = await search_kb("refunds take five business days")
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
    assert "Call search_kb before you answer" in prompts[0][0]
    assert prompts[0][1] == ["Hi", "How long do refunds take?"]


def test_a_refusal_cites_nothing(tmp_path: Path) -> None:
    async def generate(system: str, turns: list[str], search_kb: SearchTool) -> str:
        await search_kb("zebras gallop northward")
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
