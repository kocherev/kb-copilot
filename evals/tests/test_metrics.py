from kb_agent.retrieve import NOT_IN_DOCS
from kb_evals.score import (
    citation_score,
    cited_sources,
    faithfulness,
    hit_at_k,
    reciprocal_rank,
)

BILLING = "demo/docs/billing.md"
BILLING_URI = "file:///workspace/demo/docs/billing.md"
ACCOUNT_URI = "file:///workspace/demo/docs/account.html"
PASSAGE = "Refunds take 5 business days after the review team approves the request."


def test_hit_at_k_matches_a_source_inside_the_window() -> None:
    assert hit_at_k([BILLING], [BILLING_URI, ACCOUNT_URI], 5) == 1.0
    assert hit_at_k([BILLING], [ACCOUNT_URI], 5) == 0.0


def test_hit_at_k_ignores_a_match_past_k() -> None:
    retrieved = [ACCOUNT_URI] * 5 + [BILLING_URI]
    assert hit_at_k([BILLING], retrieved, 5) == 0.0


def test_hit_at_k_treats_an_empty_expectation_as_abstention() -> None:
    assert hit_at_k([], [], 5) == 1.0
    assert hit_at_k([], [BILLING_URI], 5) == 0.0


def test_reciprocal_rank_uses_the_first_matching_source() -> None:
    retrieved = [ACCOUNT_URI, BILLING_URI]
    assert reciprocal_rank([BILLING], [BILLING_URI], 5) == 1.0
    assert reciprocal_rank([BILLING], retrieved, 5) == 0.5
    assert reciprocal_rank([BILLING], [ACCOUNT_URI], 5) == 0.0
    assert reciprocal_rank([], [], 5) == 1.0
    assert reciprocal_rank([], [BILLING_URI], 5) == 0.0


def test_citation_score_requires_a_source_only_when_one_is_expected() -> None:
    assert citation_score([BILLING], [BILLING_URI]) == 1.0
    assert citation_score([BILLING], []) == 0.0
    assert citation_score([], []) == 1.0
    assert citation_score([], [BILLING_URI]) == 0.0


def test_cited_sources_reads_source_lines() -> None:
    answer = PASSAGE + "\nSource: " + BILLING_URI
    assert cited_sources(answer) == [BILLING_URI]
    assert cited_sources(NOT_IN_DOCS) == []


def test_faithfulness_accepts_a_claim_whose_tokens_are_in_the_passage() -> None:
    assert faithfulness("Refunds take 5 business days.", [PASSAGE]) == 1.0
    assert faithfulness(PASSAGE + "\nSource: " + BILLING_URI, [PASSAGE]) == 1.0


def test_faithfulness_rejects_a_number_missing_from_the_passage() -> None:
    mixed = (
        "Refunds take 5 business days after the review team approves the request. "
        "Invoices stay available for 24 months in the billing tab."
    )
    assert faithfulness("Refunds take 9 business days.", [PASSAGE]) == 0.0
    assert faithfulness("Refunds take 24 business days.", [mixed]) == 0.0


def test_refusal_is_faithful_only_when_no_passage_was_retrieved() -> None:
    assert faithfulness(NOT_IN_DOCS, []) == 1.0
    assert faithfulness(NOT_IN_DOCS, [PASSAGE]) == 0.0
