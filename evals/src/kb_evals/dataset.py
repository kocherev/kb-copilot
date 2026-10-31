import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EvalCase:
    id: str
    question: str
    answer: str
    facts: tuple[str, ...]
    sources: tuple[str, ...]


def load_dataset(path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    seen: set[str] = set()
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name}:{line_number} is not JSON") from exc
        cases.append(_case(raw, path.name, line_number, seen))
    if not cases:
        raise ValueError(f"{path.name} has no cases")
    return cases


def _case(raw: Any, name: str, line_number: int, seen: set[str]) -> EvalCase:
    where = f"{name}:{line_number}"
    if not isinstance(raw, dict):
        raise ValueError(f"{where} must be an object")
    for key in ("id", "question", "answer", "facts", "sources"):
        if key not in raw:
            raise ValueError(f"{where} {key} is required")
    case_id = raw["id"]
    question = raw["question"]
    answer = raw["answer"]
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError(f"{where} id is required")
    cleaned_id = case_id.strip()
    if cleaned_id in seen:
        raise ValueError(f"{where} duplicate id {cleaned_id}")
    seen.add(cleaned_id)
    if not isinstance(question, str) or not question.strip():
        raise ValueError(f"{where} question is required")
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError(f"{where} answer is required")
    return EvalCase(
        id=cleaned_id,
        question=question.strip(),
        answer=answer.strip(),
        facts=_strings(raw["facts"], where, "facts"),
        sources=_strings(raw["sources"], where, "sources"),
    )


def _strings(value: Any, where: str, key: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{where} {key} must be a list")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{where} {key} must be a list of strings")
        items.append(item.strip())
    return tuple(items)
