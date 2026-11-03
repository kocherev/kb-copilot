from kb_rag import Passage

POISON_MARK = "poisoned"


def matches(passage: Passage, expected: str) -> bool:
    """`billing/refunds.md` matches any chunk of the page; `#anchor` one section."""
    source, _, anchor = expected.partition("#")
    return passage.source == source and (not anchor or passage.anchor == anchor)


def recall_at_k(expected: list[str], passages: list[Passage], k: int) -> float:
    window = passages[:k]
    found = [item for item in expected if any(matches(p, item) for p in window)]
    return len(found) / len(expected)


def reciprocal_rank(expected: list[str], passages: list[Passage], k: int) -> float:
    for rank, passage in enumerate(passages[:k], start=1):
        if any(matches(passage, item) for item in expected):
            return 1.0 / rank
    return 0.0


def context_precision(expected: list[str], passages: list[Passage], k: int) -> float:
    window = passages[:k]
    if not window:
        return 0.0
    relevant = [p for p in window if any(matches(p, item) for item in expected)]
    return len(relevant) / len(window)


def fact_recall(facts: list[str], passages: list[Passage], k: int) -> float:
    context = " ".join(" ".join(p.text.split()) for p in passages[:k]).casefold()
    found = [fact for fact in facts if " ".join(fact.split()).casefold() in context]
    return len(found) / len(facts)


def poisoned_first(passages: list[Passage]) -> bool:
    return bool(passages) and POISON_MARK in passages[0].source


def precision_recall(pairs: list[tuple[bool, bool]]) -> tuple[float, float]:
    """Pairs are (expected, predicted). An empty denominator scores 0."""
    true_positive = sum(1 for expected, predicted in pairs if expected and predicted)
    predicted = sum(1 for _expected, value in pairs if value)
    expected = sum(1 for value, _predicted in pairs if value)
    precision = true_positive / predicted if predicted else 0.0
    recall = true_positive / expected if expected else 0.0
    return precision, recall


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))
    return ordered[index]
