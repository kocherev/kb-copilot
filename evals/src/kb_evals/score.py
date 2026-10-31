import re

from kb_agent.retrieve import NOT_IN_DOCS

_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def exact_match(expected: str, actual: str) -> float:
    if expected == actual:
        return 1.0
    return 0.0


def hit_at_k(expected: list[str], retrieved: list[str], k: int) -> float:
    window = _window(retrieved, k)
    abstained = _abstention(expected, window)
    if abstained is not None:
        return abstained
    if any(_matches_any(item, expected) for item in window):
        return 1.0
    return 0.0


def reciprocal_rank(expected: list[str], retrieved: list[str], k: int) -> float:
    window = _window(retrieved, k)
    abstained = _abstention(expected, window)
    if abstained is not None:
        return abstained
    for index, item in enumerate(window, start=1):
        if _matches_any(item, expected):
            return 1.0 / index
    return 0.0


def citation_score(expected: list[str], cited: list[str]) -> float:
    abstained = _abstention(expected, cited)
    if abstained is not None:
        return abstained
    if any(_matches_any(item, expected) for item in cited):
        return 1.0
    return 0.0


def cited_sources(answer: str) -> list[str]:
    found: list[str] = []
    for line in answer.splitlines():
        stripped = line.strip()
        if not stripped.startswith("Source:"):
            continue
        source = stripped.removeprefix("Source:").strip()
        if source:
            found.append(source)
    return found


def faithfulness(answer: str, passages: list[str]) -> float:
    parts = _claims(answer)
    if not parts:
        return 0.0
    context = _flat("\n".join(passages))
    supported = 0
    for claim in parts:
        if claim == NOT_IN_DOCS:
            if not passages:
                supported += 1
            continue
        if _claim_in_context(claim, context):
            supported += 1
    return supported / len(parts)


def _window(retrieved: list[str], k: int) -> list[str]:
    if k < 1:
        raise ValueError("k must be positive")
    return retrieved[:k]


def _abstention(expected: list[str], found: list[str]) -> float | None:
    if expected:
        return None
    # An empty expectation is an out-of-corpus question.
    if not found:
        return 1.0
    return 0.0


def _matches_any(retrieved: str, expected: list[str]) -> bool:
    return any(_same_source(retrieved, item) for item in expected)


def _same_source(retrieved: str, expected: str) -> bool:
    left = retrieved.replace("\\", "/").rstrip("/")
    right = expected.replace("\\", "/").strip("/")
    if not right:
        return False
    return left == right or left.endswith("/" + right)


def _claims(answer: str) -> list[str]:
    body = "\n".join(
        line for line in answer.splitlines() if not line.strip().startswith("Source:")
    ).strip()
    if not body:
        return []
    return [part.strip() for part in _SENTENCE.split(body) if part.strip()]


def _claim_in_context(claim: str, context: str) -> bool:
    body = claim.strip()
    if body.endswith((".", "!", "?")):
        body = body[:-1].rstrip()
    if not body:
        return False
    return _flat(body) in context


def _flat(text: str) -> str:
    return " ".join(text.split())
