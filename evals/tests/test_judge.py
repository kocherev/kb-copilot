import json
from pathlib import Path

import pytest
from kb_evals.dataset import EvalCase
from kb_evals.judge import (
    JUDGES,
    PROMPT_VERSION,
    Answer,
    calibrate,
    judge_prompt,
    load_answers,
    load_labeled,
    parse_verdict,
    pass_rates,
    run_judges,
)
from kb_rag import NOT_IN_DOCS, Passage

CASE = EvalCase(
    "refund",
    "answerable",
    "How long do refunds take?",
    "Refunds take 5 business days.",
    ("5 business days",),
    ("billing/refunds.md",),
    (),
)
CITED = Passage("p1", "eval", "billing/refunds.md", "", "", "Refunds take 5 days.", 1.0)
UNCITED = Passage("p2", "eval", "billing/invoices.md", "", "", "Invoices are PDF.", 0.5)
ANSWER = Answer("refund", "Refunds take 5 business days.", ("p1",))


def test_parse_verdict_reads_pass_and_reason() -> None:
    assert parse_verdict('{"pass": true, "reason": "ok"}') == (True, "ok")
    with pytest.raises(ValueError, match="boolean"):
        parse_verdict('{"pass": "yes", "reason": "ok"}')
    with pytest.raises(json.JSONDecodeError):
        parse_verdict("PASS")


def test_load_answers_validates_rows(tmp_path: Path) -> None:
    path = tmp_path / "answers.jsonl"
    path.write_text(
        '{"id": "refund", "answer": "x", "cited_passage_ids": ["p1"]}\n',
        encoding="utf-8",
    )
    assert load_answers(path) == [Answer("refund", "x", ("p1",))]

    path.write_text('{"id": "refund", "answer": "x"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="cited_passage_ids"):
        load_answers(path)


def test_citation_prompt_shows_only_cited_passages() -> None:
    prompt = judge_prompt("citation", CASE, ANSWER, [CITED, UNCITED])

    assert 'id="p1"' in prompt
    assert "Invoices are PDF." not in prompt


def test_refusal_prompt_states_the_expected_behavior() -> None:
    outside = EvalCase("fr", "off_topic", "Capital of France?", NOT_IN_DOCS, (), (), ())

    assert f"Refuse with exactly: {NOT_IN_DOCS}" in judge_prompt(
        "refusal", outside, ANSWER, []
    )
    assert "Do not refuse" in judge_prompt("refusal", CASE, ANSWER, [CITED])


def test_run_judges_asks_once_per_judge_and_scores() -> None:
    def complete(system: str, user: str) -> str:
        passed = "<required_facts>" not in user
        return json.dumps({"pass": passed, "reason": "stub"})

    verdicts = run_judges(complete, "model-x", CASE, ANSWER, [CITED])

    assert [v.judge for v in verdicts] == list(JUDGES)
    assert {(v.model, v.prompt_version) for v in verdicts} == {
        ("model-x", PROMPT_VERSION)
    }
    assert pass_rates(verdicts) == {
        "faithful": 1.0,
        "correct": 0.0,
        "refusal": 1.0,
        "citation": 1.0,
    }


def test_calibration_tpr_and_tnr() -> None:
    labels = {
        ("a", "faithful"): True,
        ("b", "faithful"): True,
        ("c", "faithful"): False,
        ("d", "faithful"): False,
        ("a", "correct"): True,
    }
    verdicts = {
        ("a", "faithful"): True,
        ("b", "faithful"): False,
        ("c", "faithful"): False,
        ("d", "faithful"): False,
        ("a", "correct"): True,
    }

    rows = {row.judge: row for row in calibrate(verdicts, labels)}

    faithful = rows["faithful"]
    assert (faithful.labeled, faithful.tpr, faithful.tnr) == (4, 0.5, 1.0)
    assert (rows["correct"].tpr, rows["correct"].tnr) == (1.0, None)
    assert rows["citation"].labeled == 0


def test_load_labeled_requires_a_known_judge(tmp_path: Path) -> None:
    path = tmp_path / "labels.jsonl"
    path.write_text('{"id": "a", "judge": "faithful", "label": true}\n', "utf-8")
    assert load_labeled(path, "label") == {("a", "faithful"): True}

    path.write_text('{"id": "a", "judge": "tone", "label": true}\n', "utf-8")
    with pytest.raises(ValueError, match="judge"):
        load_labeled(path, "label")
