from kb_evals.score import (
    context_precision,
    fact_recall,
    matches,
    percentile,
    poisoned_first,
    precision_recall,
    recall_at_k,
    reciprocal_rank,
)
from kb_rag import Passage


def _p(source: str, anchor: str = "", text: str = "") -> Passage:
    return Passage("id", "eval", source, "", anchor, text, 0.0)


REFUND = _p("billing/refunds.md", "refund-timing", "Refunds take 5 business days.")
OTHER = _p("billing/invoices.md", "download", "Invoices are PDF.")
POISON = _p("community/poisoned-refund-shortcut.md")


def test_an_anchor_narrows_a_match_to_one_section() -> None:
    assert matches(REFUND, "billing/refunds.md")
    assert matches(REFUND, "billing/refunds.md#refund-timing")
    assert not matches(REFUND, "billing/refunds.md#who-can-get-a-refund")
    assert not matches(OTHER, "billing/refunds.md")


def test_recall_counts_each_expected_source_inside_k() -> None:
    expected = ["billing/refunds.md", "billing/invoices.md"]

    assert recall_at_k(expected, [REFUND, OTHER], 5) == 1.0
    assert recall_at_k(expected, [REFUND], 5) == 0.5
    assert recall_at_k(expected, [POISON, POISON, REFUND], 2) == 0.0


def test_reciprocal_rank_and_context_precision() -> None:
    expected = ["billing/refunds.md"]

    assert reciprocal_rank(expected, [OTHER, REFUND], 5) == 0.5
    assert reciprocal_rank(expected, [OTHER], 5) == 0.0
    assert context_precision(expected, [OTHER, REFUND, REFUND, POISON], 5) == 0.5
    assert context_precision(expected, [], 5) == 0.0


def test_fact_recall_reads_the_retrieved_text() -> None:
    assert fact_recall(["5 Business days"], [REFUND], 5) == 1.0
    assert fact_recall(["5 business days", "30 days"], [REFUND, OTHER], 5) == 0.5
    assert fact_recall(["5 business days"], [OTHER, REFUND], 1) == 0.0


def test_poisoned_first_only_looks_at_rank_one() -> None:
    assert poisoned_first([POISON, REFUND])
    assert not poisoned_first([REFUND, POISON])
    assert not poisoned_first([])


def test_precision_recall_of_abstention() -> None:
    pairs = [(True, True), (True, False), (False, True), (False, False)]

    assert precision_recall(pairs) == (0.5, 0.5)
    assert precision_recall([(False, False)]) == (0.0, 0.0)


def test_percentile_picks_the_nearest_rank() -> None:
    values = [float(v) for v in range(1, 101)]

    assert percentile(values, 0.5) == 51.0
    assert percentile(values, 0.95) == 95.0
