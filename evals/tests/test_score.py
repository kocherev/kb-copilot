from kb_evals.score import exact_match


def test_exact_match_scores_equal_strings() -> None:
    assert exact_match("refund in 5 days", "refund in 5 days") == 1.0


def test_exact_match_scores_any_difference_as_zero() -> None:
    assert exact_match("refund in 5 days", "refund in five days") == 0.0
