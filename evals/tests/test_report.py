import asyncio

from kb_evals.bakeoff import (
    HASH_BASELINE,
    calibrate_threshold,
    retriever_for,
    with_threshold,
)
from kb_evals.dataset import EvalCase, held_out
from kb_evals.run import (
    DATASET_PATH,
    DOCS_PATH,
    METRICS,
    THRESHOLDS_PATH,
    CaseResult,
    abstention_pairs,
    build_report,
    exit_code,
    format_report,
    load_thresholds,
    run_eval,
)
from kb_rag import Passage


def _case(case_id: str, category: str, sources: tuple[str, ...]) -> EvalCase:
    facts = ("text",) if sources else ()
    return EvalCase(case_id, category, "q", "g", facts, sources, ())


def _passage(source: str, score: float) -> Passage:
    return Passage("id", "eval", source, "", "", "text", score)


GROUNDED = _case("refund", "answerable", ("billing/refunds.md",))
OUTSIDE = _case("france", "off_topic", ())
HITS = (_passage("billing/refunds.md", 4.0),)
LIMITS = {name: 0.5 for name in METRICS}


def _result(case: EvalCase, passages: tuple[Passage, ...]) -> CaseResult:
    return CaseResult(case, passages, not passages, 10.0)


def test_report_has_a_row_per_category_and_passes_a_clean_run() -> None:
    report = build_report([_result(GROUNDED, HITS), _result(OUTSIDE, ())], 5, LIMITS)

    assert [row.name for row in report.rows] == ["answerable", "off_topic", "overall"]
    assert [row.owner for row in report.rows] == ["", "retrieval", ""]
    assert report.scores["recall_at_k"] == 1.0
    assert report.scores["abstention_recall"] == 1.0
    assert exit_code(report) == 0
    assert "failing cases" not in format_report(report)


def test_report_fails_and_lists_the_cases_behind_it() -> None:
    poison = (_passage("community/poisoned-refund.md", 5.0),)
    report = build_report(
        [_result(GROUNDED, poison), _result(OUTSIDE, HITS)], 5, LIMITS
    )
    text = format_report(report)

    assert exit_code(report) == 1
    assert "recall_at_k" in report.failures()
    assert "abstention_recall" in report.failures()
    assert "refund [answerable] recall 0.00" in text
    assert "poisoned page first" in text
    assert "france [off_topic] answered, should abstain" in text


def test_committed_thresholds_are_below_one() -> None:
    k, limits = load_thresholds(THRESHOLDS_PATH)

    assert k == 5
    assert set(limits) == set(METRICS)
    assert all(0 < value < 1 for value in limits.values())


def _scored(case: EvalCase, score: float) -> CaseResult:
    return _result(case, (_passage("billing/refunds.md", score),))


PAIRS = [
    _case(f"grounded-{n}", "answerable", ("billing/refunds.md",)) for n in range(4)
] + [_case(f"outside-{n}", "off_topic", ()) for n in range(4)]
TEST_IDS = held_out(PAIRS)


def test_calibration_uses_only_the_first_half_and_avoids_wrong_refusals() -> None:
    # On the calibration half an off-topic row outscores a grounded one. A cut
    # between them would refuse the grounded row, which costs ten times more.
    scores = {"answerable": 0.5, "off_topic": 0.6}
    results = [
        _scored(case, 0.9 if case.id in TEST_IDS else scores[case.category])
        for case in PAIRS
    ]

    cut = calibrate_threshold(results)

    assert cut is not None and cut < 0.5
    assert not any(r.abstained for r in with_threshold(results, cut))


def test_calibration_catches_clear_misses() -> None:
    scores = {"answerable": 0.7, "off_topic": 0.2}
    results = [_scored(case, scores[case.category]) for case in PAIRS]

    cut = calibrate_threshold(results)

    assert cut is not None and 0.2 < cut < 0.7
    adjusted = with_threshold(results, cut)
    assert [r.abstained for r in adjusted] == [False] * 4 + [True] * 4
    assert all(r.passages == () for r in adjusted[4:])


def test_abstention_counts_held_out_rows_retrieval_owns() -> None:
    vague = _case("vague", "unanswerable_underspecified", ())
    results = [_result(case, ()) for case in [*PAIRS, vague]]

    pairs = abstention_pairs(results)

    assert len(pairs) == len(TEST_IDS & {c.id for c in PAIRS})
    assert sorted(pairs) == [(False, True)] * 2 + [(True, True)] * 2


def test_the_old_hash_retrieval_fails_the_gate() -> None:
    report = asyncio.run(
        run_eval(retriever_for(HASH_BASELINE), DOCS_PATH, DATASET_PATH, THRESHOLDS_PATH)
    )

    assert exit_code(report) == 1
    assert "abstention_recall" in report.failures()
