from pathlib import Path

import pytest
from kb_agent.retrieve import NOT_IN_DOCS
from kb_evals.dataset import load_dataset
from kb_evals.run import (
    DATASET_PATH,
    DOCS_PATH,
    ROOT,
    THRESHOLDS_PATH,
    CaseScore,
    Report,
    answer_turn,
    exit_code,
    format_report,
    index_demo,
    load_thresholds,
    run_eval,
)


def test_dataset_rejects_a_row_without_a_question(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    path.write_text(
        '{"id":"a","answer":"x","facts":[],"sources":[]}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="question"):
        load_dataset(path)


def test_demo_dataset_has_at_least_30_grounded_rows() -> None:
    cases = load_dataset(DATASET_PATH)
    refusals = [case for case in cases if not case.sources]
    grounded = [case for case in cases if case.sources]

    assert len(cases) >= 30
    assert refusals
    assert grounded
    for case in refusals:
        assert case.answer == NOT_IN_DOCS
        assert case.facts == ()
    for case in grounded:
        assert case.facts
        assert case.answer != NOT_IN_DOCS
        for fact in case.facts:
            assert fact in case.answer
        for source in case.sources:
            assert (ROOT / source).is_file()


def test_thresholds_name_the_four_metrics() -> None:
    k, limits = load_thresholds(THRESHOLDS_PATH)
    assert k == 5
    assert set(limits) == {"hit_at_k", "mrr", "citation_rate", "faithfulness"}
    assert all(value > 0 for value in limits.values())


def test_refund_cites_billing_and_an_outside_question_does_not() -> None:
    client = index_demo(DOCS_PATH)
    refund = answer_turn(
        client,
        "How long do refunds take?",
        "Refunds take 5 business days after the review team approves the request.",
        5,
    )
    outside = answer_turn(client, "What is the capital of France?", NOT_IN_DOCS, 5)

    assert "5 business days" in refund.text
    assert "Source:" in refund.text
    assert "billing.md" in refund.text
    assert outside.text == NOT_IN_DOCS
    assert "Source:" not in outside.text
    assert outside.retrieved == ()


def test_format_report_names_each_metric_and_a_miss() -> None:
    missed = CaseScore("refund-days", 1.0, 0.5, 1.0, 1.0)
    report = Report(
        k=5,
        scores={
            "hit_at_k": 1.0,
            "mrr": 0.5,
            "citation_rate": 1.0,
            "faithfulness": 1.0,
        },
        thresholds={
            "hit_at_k": 1.0,
            "mrr": 1.0,
            "citation_rate": 1.0,
            "faithfulness": 1.0,
        },
        case_scores=(missed,),
    )
    text = format_report(report)

    assert "hit@5" in text
    assert "mrr" in text
    assert "citation_rate" in text
    assert "faithfulness" in text
    assert "below threshold: mrr 0.500 < 1.000" in text
    assert "case refund-days" in text
    assert exit_code(report) == 1


def test_format_report_hides_cases_when_the_gate_passes() -> None:
    perfect = CaseScore("refund-days", 1.0, 1.0, 1.0, 1.0)
    scores = {
        "hit_at_k": 1.0,
        "mrr": 1.0,
        "citation_rate": 1.0,
        "faithfulness": 1.0,
    }
    report = Report(k=5, scores=scores, thresholds=scores, case_scores=(perfect,))
    assert "case " not in format_report(report)
    assert exit_code(report) == 0


def test_demo_eval_meets_committed_thresholds() -> None:
    report = run_eval(DOCS_PATH, DATASET_PATH, THRESHOLDS_PATH)
    assert report.failures() == [], format_report(report)
