import json
from dataclasses import dataclass
from pathlib import Path

from kb_agent.retrieve import NOT_IN_DOCS, citation_suffix, search_kb
from kb_rag.pipeline import index_sources
from kb_rag.sources import iter_documents, read_source
from qdrant_client import QdrantClient

from kb_evals.dataset import EvalCase, load_dataset
from kb_evals.score import (
    citation_score,
    cited_sources,
    faithfulness,
    hit_at_k,
    reciprocal_rank,
)

ROOT = Path(__file__).resolve().parents[3]
DATASET_PATH = ROOT / "evals" / "datasets" / "demo.jsonl"
THRESHOLDS_PATH = ROOT / "evals" / "thresholds.json"
DOCS_PATH = ROOT / "demo" / "docs"
PRODUCT_ID = "demo"
METRIC_ORDER = ("hit_at_k", "mrr", "citation_rate", "faithfulness")


@dataclass(frozen=True)
class CaseScore:
    id: str
    hit_at_k: float
    mrr: float
    citation_rate: float
    faithfulness: float


@dataclass(frozen=True)
class Turn:
    text: str
    retrieved: tuple[str, ...]
    passages: tuple[str, ...]


@dataclass(frozen=True)
class Report:
    k: int
    scores: dict[str, float]
    thresholds: dict[str, float]
    case_scores: tuple[CaseScore, ...]

    @property
    def cases(self) -> int:
        return len(self.case_scores)

    def failures(self) -> list[str]:
        return [
            name for name in METRIC_ORDER if self.scores[name] < self.thresholds[name]
        ]


def index_demo(docs: Path) -> QdrantClient:
    client = QdrantClient(":memory:")
    paths = iter_documents(docs)
    if not paths:
        raise ValueError(f"no documents in {docs}")
    index_sources(client, PRODUCT_ID, [read_source(path) for path in paths])
    return client


def answer_turn(client: QdrantClient, question: str, recorded: str, k: int) -> Turn:
    found = search_kb(client, PRODUCT_ID, question, limit=k)
    retrieved = tuple(hit.source_url for hit in found.hits)
    passages = tuple(hit.text for hit in found.hits)
    if not found.hits:
        return Turn(text=NOT_IN_DOCS, retrieved=retrieved, passages=passages)
    text = recorded.rstrip() + citation_suffix(found.source_urls())
    return Turn(text=text, retrieved=retrieved, passages=passages)


def load_thresholds(path: Path) -> tuple[int, dict[str, float]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("thresholds must be an object")
    k = raw.get("k")
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k must be a positive integer")
    limits: dict[str, float] = {}
    for name in METRIC_ORDER:
        value = raw.get(name)
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"{name} must be a number")
        score = float(value)
        if not 0 <= score <= 1:
            raise ValueError(f"{name} must be between 0 and 1")
        limits[name] = score
    return k, limits


def run_eval(docs: Path, dataset: Path, thresholds: Path) -> Report:
    k, limits = load_thresholds(thresholds)
    cases = load_dataset(dataset)
    client = index_demo(docs)
    scored = tuple(_score_case(client, case, k) for case in cases)
    return Report(
        k=k,
        scores=_means(scored),
        thresholds=limits,
        case_scores=scored,
    )


def format_report(report: Report) -> str:
    rows = [
        f"cases {report.cases}",
        f"{'metric':<16}{'score':>8}{'threshold':>12}",
    ]
    for name in METRIC_ORDER:
        label = _label(name, report.k)
        rows.append(
            f"{label:<16}{report.scores[name]:>8.3f}{report.thresholds[name]:>12.3f}"
        )
    for name in report.failures():
        label = _label(name, report.k)
        rows.append(
            f"below threshold: {label} "
            f"{report.scores[name]:.3f} < {report.thresholds[name]:.3f}"
        )
    if report.failures():
        for case in report.case_scores:
            if min(case.hit_at_k, case.mrr, case.citation_rate, case.faithfulness) < 1:
                rows.append(
                    f"case {case.id} hit={case.hit_at_k:.3f} "
                    f"mrr={case.mrr:.3f} citation={case.citation_rate:.3f} "
                    f"faith={case.faithfulness:.3f}"
                )
    return "\n".join(rows)


def exit_code(report: Report) -> int:
    if report.failures():
        return 1
    return 0


def main() -> int:
    report = run_eval(DOCS_PATH, DATASET_PATH, THRESHOLDS_PATH)
    print(format_report(report))
    return exit_code(report)


def _score_case(client: QdrantClient, case: EvalCase, k: int) -> CaseScore:
    turn = answer_turn(client, case.question, case.answer, k)
    expected = list(case.sources)
    retrieved = list(turn.retrieved)
    return CaseScore(
        id=case.id,
        hit_at_k=hit_at_k(expected, retrieved, k),
        mrr=reciprocal_rank(expected, retrieved, k),
        citation_rate=citation_score(expected, cited_sources(turn.text)),
        faithfulness=faithfulness(turn.text, list(turn.passages)),
    )


def _means(cases: tuple[CaseScore, ...]) -> dict[str, float]:
    count = len(cases)
    return {
        "hit_at_k": sum(case.hit_at_k for case in cases) / count,
        "mrr": sum(case.mrr for case in cases) / count,
        "citation_rate": sum(case.citation_rate for case in cases) / count,
        "faithfulness": sum(case.faithfulness for case in cases) / count,
    }


def _label(name: str, k: int) -> str:
    if name == "hit_at_k":
        return f"hit@{k}"
    return name
