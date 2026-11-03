import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

from kb_rag import (
    DEFAULT_SETTINGS,
    Passage,
    RetrievalSettings,
    SearchResult,
    Source,
    index_sources,
    read_directory,
    search,
)
from qdrant_client import AsyncQdrantClient

from kb_evals.dataset import (
    ANSWER_LAYER,
    CATEGORIES,
    RETRIEVAL_ABSTAIN,
    EvalCase,
    held_out,
    load_dataset,
)
from kb_evals.score import (
    context_precision,
    fact_recall,
    percentile,
    poisoned_first,
    precision_recall,
    recall_at_k,
    reciprocal_rank,
)

ROOT = Path(__file__).resolve().parents[3]
DATASET_PATH = ROOT / "evals" / "datasets" / "v1.jsonl"
THRESHOLDS_PATH = ROOT / "evals" / "thresholds.json"
DOCS_PATH = ROOT / "demo" / "docs"
PRODUCT_ID = "eval"
METRICS = (
    "recall_at_k",
    "mrr",
    "context_precision",
    "fact_recall",
    "abstention_precision",
    "abstention_recall",
    "injection_safety",
)


class RagRetriever:
    """The production path: kb_rag over an in-memory Qdrant."""

    def __init__(
        self,
        settings: RetrievalSettings = DEFAULT_SETTINGS,
        client: AsyncQdrantClient | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or AsyncQdrantClient(":memory:")

    async def index(self, sources: list[Source]) -> None:
        await index_sources(self.client, PRODUCT_ID, sources, settings=self.settings)

    async def search(self, query: str, limit: int) -> SearchResult:
        return await search(
            self.client, PRODUCT_ID, query, limit=limit, settings=self.settings
        )


@dataclass(frozen=True)
class CaseResult:
    case: EvalCase
    passages: tuple[Passage, ...]
    abstained: bool
    latency_ms: float


@dataclass(frozen=True)
class Row:
    name: str
    owner: str
    cases: int
    recall_at_k: float | None
    mrr: float | None
    context_precision: float | None
    fact_recall: float | None
    abstain_rate: float
    injection_safety: float


@dataclass(frozen=True)
class Report:
    k: int
    rows: tuple[Row, ...]
    scores: dict[str, float]
    thresholds: dict[str, float]
    misses: tuple[str, ...]
    latency_p50_ms: float
    latency_p95_ms: float

    def failures(self) -> list[str]:
        return [name for name in METRICS if self.scores[name] < self.thresholds[name]]


def load_thresholds(path: Path) -> tuple[int, dict[str, float]]:
    raw = json.loads(path.read_text("utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("thresholds must be an object")
    k = raw.get("k")
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k must be a positive integer")
    limits: dict[str, float] = {}
    for name in METRICS:
        value = raw.get(name)
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"{name} must be a number")
        if not 0 <= value <= 1:
            raise ValueError(f"{name} must be between 0 and 1")
        limits[name] = float(value)
    return k, limits


async def collect(
    retriever: RagRetriever, cases: list[EvalCase], k: int
) -> list[CaseResult]:
    results: list[CaseResult] = []
    for case in cases:
        found = await retriever.search(case.query, k)
        results.append(
            CaseResult(
                case=case,
                passages=found.passages,
                abstained=found.abstained,
                latency_ms=found.timings_ms["total"],
            )
        )
    return results


def build_report(
    results: list[CaseResult], k: int, thresholds: dict[str, float]
) -> Report:
    rows = [
        _row(name, [r for r in results if r.case.category == name], k)
        for name in CATEGORIES
        if any(r.case.category == name for r in results)
    ]
    overall = _row("overall", results, k)
    precision, recall = precision_recall(abstention_pairs(results))
    scores = {
        "recall_at_k": overall.recall_at_k or 0.0,
        "mrr": overall.mrr or 0.0,
        "context_precision": overall.context_precision or 0.0,
        "fact_recall": overall.fact_recall or 0.0,
        "abstention_precision": precision,
        "abstention_recall": recall,
        "injection_safety": overall.injection_safety,
    }
    latencies = [r.latency_ms for r in results]
    return Report(
        k=k,
        rows=(*rows, overall),
        scores=scores,
        thresholds=thresholds,
        misses=tuple(m for r in results if (m := _miss(r, k))),
        latency_p50_ms=percentile(latencies, 0.5),
        latency_p95_ms=percentile(latencies, 0.95),
    )


async def run_eval(
    retriever: RagRetriever, docs: Path, dataset: Path, thresholds: Path
) -> Report:
    k, limits = load_thresholds(thresholds)
    cases = load_dataset(dataset)
    await retriever.index(read_directory(docs))
    return build_report(await collect(retriever, cases, k), k, limits)


def format_report(report: Report) -> str:
    k = report.k
    header = (
        f"{'category':<30}{'owner':<10}{'n':>4}{f'recall@{k}':>10}{'mrr':>7}"
        f"{'ctx_prec':>10}{'facts':>7}{'abstain':>9}{'inj_safe':>10}"
    )
    lines = [header]
    for row in report.rows:
        lines.append(
            f"{row.name:<30}{row.owner:<10}{row.cases:>4}"
            f"{_cell(row.recall_at_k, 10)}"
            f"{_cell(row.mrr, 7)}{_cell(row.context_precision, 10)}"
            f"{_cell(row.fact_recall, 7)}{_cell(row.abstain_rate, 9)}"
            f"{_cell(row.injection_safety, 10)}"
        )
    lines.append("")
    lines.append(
        f"latency p50 {report.latency_p50_ms:.1f} ms"
        f"  p95 {report.latency_p95_ms:.1f} ms"
    )
    lines.append(
        "owner: retrieval should abstain; answer is judged live on the model's "
        "reply. Abstention precision and recall use the held-out half only."
    )
    lines.append(f"{'gate':<28}{'score':>8}{'threshold':>11}")
    for name in METRICS:
        mark = "  FAIL" if name in report.failures() else ""
        lines.append(
            f"{name:<28}{report.scores[name]:>8.3f}"
            f"{report.thresholds[name]:>11.3f}{mark}"
        )
    if report.failures():
        lines.append("")
        lines.append(f"failing cases ({len(report.misses)}):")
        lines.extend(f"  {miss}" for miss in report.misses)
    return "\n".join(lines)


def exit_code(report: Report) -> int:
    return 1 if report.failures() else 0


def abstention_pairs(results: list[CaseResult]) -> list[tuple[bool, bool]]:
    """(should abstain, did abstain) for held-out rows where retrieval decides."""
    test = held_out([r.case for r in results])
    pairs: list[tuple[bool, bool]] = []
    for result in results:
        label = result.case.abstain_label
        if label is not None and result.case.id in test:
            pairs.append((label, result.abstained))
    return pairs


def _row(name: str, results: list[CaseResult], k: int) -> Row:
    grounded = [r for r in results if r.case.expected_sources]
    with_facts = [r for r in results if r.case.required_facts]

    def score(rows: list[CaseResult], metric) -> float | None:
        return mean(metric(r) for r in rows) if rows else None

    owner = (
        "retrieval"
        if name in RETRIEVAL_ABSTAIN
        else "answer"
        if name in ANSWER_LAYER
        else ""
    )
    return Row(
        name=name,
        owner=owner,
        cases=len(results),
        recall_at_k=score(
            grounded,
            lambda r: recall_at_k(list(r.case.expected_sources), list(r.passages), k),
        ),
        mrr=score(
            grounded,
            lambda r: reciprocal_rank(
                list(r.case.expected_sources), list(r.passages), k
            ),
        ),
        context_precision=score(
            grounded,
            lambda r: context_precision(
                list(r.case.expected_sources), list(r.passages), k
            ),
        ),
        fact_recall=score(
            with_facts,
            lambda r: fact_recall(list(r.case.required_facts), list(r.passages), k),
        ),
        abstain_rate=mean(1.0 if r.abstained else 0.0 for r in results),
        injection_safety=mean(
            0.0 if poisoned_first(list(r.passages)) else 1.0 for r in results
        ),
    )


def _miss(result: CaseResult, k: int) -> str:
    case = result.case
    problems: list[str] = []
    if case.should_abstain and not result.abstained:
        top = result.passages[0]
        problems.append(f"answered, should abstain (top {top.source} {top.score:.2f})")
    elif case.abstain_label is False and result.abstained:
        problems.append("abstained on a grounded question")
    elif case.expected_sources:
        recall = recall_at_k(list(case.expected_sources), list(result.passages), k)
        if recall < 1:
            got = ", ".join(p.source for p in result.passages[:3])
            problems.append(f"recall {recall:.2f} (top: {got})")
    if poisoned_first(list(result.passages)):
        problems.append(f"poisoned page first: {result.passages[0].source}")
    if not problems:
        return ""
    return f"{case.id} [{case.category}] " + "; ".join(problems)


def _cell(value: float | None, width: int) -> str:
    return f"{'-':>{width}}" if value is None else f"{value:>{width}.3f}"
