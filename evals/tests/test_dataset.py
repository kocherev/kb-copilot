import json
from pathlib import Path

import pytest
from kb_evals.dataset import CATEGORIES, RETRIEVAL_ABSTAIN, held_out, load_dataset
from kb_evals.run import DATASET_PATH, DOCS_PATH
from kb_evals.score import POISON_MARK
from kb_rag.chunk import chunk_text
from kb_rag.pipeline import _page_title
from kb_rag.sources import iter_documents, read_source

NO_SOURCES = {"off_topic", "unanswerable_out_of_scope", "unanswerable_underspecified"}


def _row(**fields: object) -> str:
    base = {
        "id": "a",
        "category": "answerable",
        "question": "q",
        "gold_answer": "g",
        "required_facts": [],
        "expected_sources": [],
        "turns": [],
    }
    return json.dumps({**base, **fields}) + "\n"


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"question": " "}, "question"),
        ({"category": "trivia"}, "unknown category"),
        ({"expected_sources": "billing.md"}, "expected_sources"),
    ],
)
def test_dataset_rejects_bad_rows(tmp_path: Path, fields: dict, message: str) -> None:
    path = tmp_path / "cases.jsonl"
    path.write_text(_row(**fields), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_dataset(path)


def test_dataset_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    path.write_text(_row() + _row(), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate"):
        load_dataset(path)


def test_follow_up_query_carries_earlier_turns(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    path.write_text(
        _row(category="follow_up", question="And yearly?", turns=["Team price?"]),
        encoding="utf-8",
    )

    assert load_dataset(path)[0].query == "Team price? And yearly?"


def test_v1_rows_point_at_real_sections_and_facts() -> None:
    cases = load_dataset(DATASET_PATH)
    chunks = {}
    for path in iter_documents(DOCS_PATH):
        source = read_source(path, DOCS_PATH)
        chunks[source.source] = chunk_text(
            source.text, markdown=source.markdown, title=_page_title(source.source)
        )

    assert len(cases) >= 150
    assert {case.category for case in cases} == set(CATEGORIES)
    for case in cases:
        assert case.should_abstain == (case.category in RETRIEVAL_ABSTAIN), case.id
        assert (not case.expected_sources) == (case.category in NO_SOURCES), case.id
        assert bool(case.turns) == (case.category == "follow_up"), case.id
        context = ""
        for expected in case.expected_sources:
            source, _, anchor = expected.partition("#")
            assert POISON_MARK not in source, case.id
            assert source in chunks, f"{case.id}: {source}"
            section = [c for c in chunks[source] if not anchor or c.anchor == anchor]
            assert section, f"{case.id}: {expected}"
            context += " ".join(c.text for c in section).casefold()
        for fact in case.required_facts:
            assert fact.casefold() in context, f"{case.id}: {fact}"


def test_held_out_split_is_stable_and_stratified() -> None:
    cases = load_dataset(DATASET_PATH)
    test = held_out(cases)

    assert test == held_out(list(reversed(cases)))
    for category in CATEGORIES:
        ids = [c.id for c in cases if c.category == category]
        assert len(test & set(ids)) == len(ids) - len(ids) // 2
