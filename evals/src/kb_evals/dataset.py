import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CATEGORIES = (
    "answerable",
    "paraphrase",
    "multi_hop",
    "follow_up",
    "off_topic",
    "unanswerable_out_of_scope",
    "unanswerable_false_premise",
    "unanswerable_underspecified",
    "unanswerable_partial",
    "injection",
)
# Retrieval should abstain on these. The answer model, with passages in front
# of it, handles the other unanswerable kinds.
RETRIEVAL_ABSTAIN = frozenset({"off_topic", "unanswerable_out_of_scope"})
ANSWER_LAYER = frozenset(
    {
        "unanswerable_false_premise",
        "unanswerable_underspecified",
        "unanswerable_partial",
    }
)
SPLIT_SEED = "kb-evals-v1"
_LISTS = ("required_facts", "expected_sources", "turns")


@dataclass(frozen=True)
class EvalCase:
    id: str
    category: str
    question: str
    gold_answer: str
    required_facts: tuple[str, ...]
    expected_sources: tuple[str, ...]
    turns: tuple[str, ...]

    @property
    def should_abstain(self) -> bool:
        return self.category in RETRIEVAL_ABSTAIN

    @property
    def abstain_label(self) -> bool | None:
        """True: retrieval should abstain. False: it must not. None: not its call."""
        if self.should_abstain:
            return True
        return False if self.expected_sources else None

    @property
    def query(self) -> str:
        """Earlier turns are prepended because the offline run has no rewriter."""
        return " ".join((*self.turns, self.question))


def held_out(cases: list[EvalCase]) -> frozenset[str]:
    """Ids of the test half: per category, order ids by a seeded hash, keep the
    second half. The first half calibrates the abstain threshold."""
    test: set[str] = set()
    for category in CATEGORIES:
        ids = sorted(
            (c.id for c in cases if c.category == category),
            key=lambda case_id: hashlib.sha256(
                f"{SPLIT_SEED}:{case_id}".encode()
            ).hexdigest(),
        )
        test.update(ids[len(ids) // 2 :])
    return frozenset(test)


def load_dataset(path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    seen: set[str] = set()
    for line_number, line in enumerate(path.read_text("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        where = f"{path.name}:{line_number}"
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{where} is not JSON") from exc
        case = _case(raw, where)
        if case.id in seen:
            raise ValueError(f"{where} duplicate id {case.id}")
        seen.add(case.id)
        cases.append(case)
    if not cases:
        raise ValueError(f"{path.name} has no cases")
    return cases


def _case(raw: Any, where: str) -> EvalCase:
    if not isinstance(raw, dict):
        raise ValueError(f"{where} must be an object")
    texts: dict[str, str] = {}
    for key in ("id", "category", "question", "gold_answer"):
        value = raw.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{where} {key} is required")
        texts[key] = value.strip()
    if texts["category"] not in CATEGORIES:
        raise ValueError(f"{where} unknown category {texts['category']}")
    lists = {key: _strings(raw.get(key), where, key) for key in _LISTS}
    return EvalCase(
        id=texts["id"],
        category=texts["category"],
        question=texts["question"],
        gold_answer=texts["gold_answer"],
        required_facts=lists["required_facts"],
        expected_sources=lists["expected_sources"],
        turns=lists["turns"],
    )


def _strings(value: Any, where: str, key: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(f"{where} {key} must be a list of strings")
    return tuple(item.strip() for item in value)
