"""Compare retrieval configs on the v1 dataset. `make bakeoff` runs main()."""

import argparse
import asyncio
import time
import warnings
from dataclasses import dataclass, replace

from kb_rag import (
    FastEmbedDense,
    FastEmbedReranker,
    FastEmbedSparse,
    RetrievalSettings,
    read_directory,
    should_abstain,
    testing,
)
from qdrant_client import AsyncQdrantClient

from kb_evals.dataset import held_out, load_dataset
from kb_evals.run import (
    DATASET_PATH,
    DOCS_PATH,
    THRESHOLDS_PATH,
    CaseResult,
    RagRetriever,
    Report,
    build_report,
    collect,
    load_thresholds,
)

DENSE_MODELS = (
    "BAAI/bge-small-en-v1.5",
    "google/embeddinggemma-300m",
    "Qwen/Qwen3-Embedding-0.6B-Q",
)
SPARSE_MODELS = ("Qdrant/bm25", "Qdrant/minicoil-v1")
RERANK_MODELS = (None, "Xenova/ms-marco-MiniLM-L-12-v2", "BAAI/bge-reranker-base")
HASH_BASELINE = "hash-baseline"
# A wrong refusal loses an answer the docs have; passing an off-topic question
# on costs one model reply that can still refuse.
FALSE_REFUSAL_COST = 10.0
# The retrieval that shipped before FastEmbed: hashed tokens, no abstention.
HASH_SETTINGS = replace(testing.HASH_SETTINGS, abstain_threshold=None)


def retriever_for(name: str) -> RagRetriever:
    if name == "default":
        return RagRetriever()
    if name == HASH_BASELINE:
        return RagRetriever(HASH_SETTINGS)
    raise ValueError(f"unknown config {name}; use default or {HASH_BASELINE}")


def calibrate_threshold(results: list[CaseResult]) -> float | None:
    """The cutoff with the lowest asymmetric cost on the calibration half.

    Only rows where retrieval decides count: should-abstain rows against
    grounded rows. Ties go to the lower cutoff, which refuses less.
    """
    test = held_out([r.case for r in results])
    rows = [
        r
        for r in results
        if r.case.id not in test and r.case.abstain_label is not None and r.passages
    ]
    tops = sorted({max(p.score for p in r.passages) for r in rows})
    if not tops:
        return None
    cuts = [
        tops[0] - 1.0,
        *((a + b) / 2 for a, b in zip(tops, tops[1:], strict=False)),
    ]

    def cost(cut: float) -> float:
        total = 0.0
        for r in rows:
            refused = should_abstain(r.passages, cut)
            if refused and not r.case.abstain_label:
                total += FALSE_REFUSAL_COST
            elif not refused and r.case.abstain_label:
                total += 1.0
        return total

    return round(min(cuts, key=lambda cut: (cost(cut), cut)), 3)


def with_threshold(results: list[CaseResult], cut: float | None) -> list[CaseResult]:
    adjusted: list[CaseResult] = []
    for result in results:
        abstained = should_abstain(result.passages, cut)
        adjusted.append(
            replace(
                result,
                abstained=abstained,
                passages=() if abstained else result.passages,
            )
        )
    return adjusted


@dataclass(frozen=True)
class Outcome:
    """report applies the threshold; raw is the same ranking with no abstain."""

    name: str
    threshold: float | None
    index_seconds: float
    report: Report
    raw: Report


async def _bakeoff(
    dense_models: list[str], sparse_models: list[str], rerank_models: list[str | None]
) -> list[Outcome]:
    k, limits = load_thresholds(THRESHOLDS_PATH)
    cases = load_dataset(DATASET_PATH)
    sources = read_directory(DOCS_PATH)
    outcomes: list[Outcome] = []

    started = time.perf_counter()
    baseline = RagRetriever(HASH_SETTINGS)
    await baseline.index(sources)
    indexed = time.perf_counter() - started
    report = build_report(await collect(baseline, cases, k), k, limits)
    outcomes.append(Outcome(HASH_BASELINE, None, indexed, report, report))
    _print_outcome(outcomes[-1])

    for dense in dense_models:
        for sparse in sparse_models:
            base = RetrievalSettings(
                dense=FastEmbedDense(dense),
                sparse=FastEmbedSparse(sparse),
                reranker=None,
                abstain_threshold=None,
            )
            client = AsyncQdrantClient(":memory:")
            started = time.perf_counter()
            await RagRetriever(base, client).index(sources)
            indexed = time.perf_counter() - started
            for rerank in rerank_models:
                settings = replace(
                    base, reranker=FastEmbedReranker(rerank) if rerank else None
                )
                raw = await collect(RagRetriever(settings, client), cases, k)
                cut = calibrate_threshold(raw)
                report = build_report(with_threshold(raw, cut), k, limits)
                name = f"{dense} + {sparse} + {rerank or 'no rerank'}"
                outcomes.append(
                    Outcome(name, cut, indexed, report, build_report(raw, k, limits))
                )
                _print_outcome(outcomes[-1])
    return outcomes


_HEADER = (
    f"{'config':<64}{'raw_rec':>8}{'raw_para':>9}{'recall':>8}{'para':>7}"
    f"{'mrr':>7}{'facts':>7}{'abstP':>7}{'abstR':>7}{'inj':>7}{'cut':>8}"
    f"{'index_s':>9}{'p50_ms':>9}{'p95_ms':>9}"
)


def _print_outcome(outcome: Outcome) -> None:
    print(format_line(outcome), flush=True)


def _paraphrase(report: Report) -> float:
    row = next((r for r in report.rows if r.name == "paraphrase"), None)
    return (row.recall_at_k or 0.0) if row else 0.0


def format_line(outcome: Outcome) -> str:
    scores = outcome.report.scores
    cut = "-" if outcome.threshold is None else f"{outcome.threshold:.3f}"
    return (
        f"{outcome.name:<64}{outcome.raw.scores['recall_at_k']:>8.3f}"
        f"{_paraphrase(outcome.raw):>9.3f}"
        f"{scores['recall_at_k']:>8.3f}{_paraphrase(outcome.report):>7.3f}"
        f"{scores['mrr']:>7.3f}{scores['fact_recall']:>7.3f}"
        f"{scores['abstention_precision']:>7.3f}"
        f"{scores['abstention_recall']:>7.3f}"
        f"{scores['injection_safety']:>7.3f}{cut:>8}"
        f"{outcome.index_seconds:>9.1f}"
        f"{outcome.report.latency_p50_ms:>9.1f}"
        f"{outcome.report.latency_p95_ms:>9.1f}"
    )


def format_table(outcomes: list[Outcome]) -> str:
    return "\n".join([_HEADER, *(format_line(outcome) for outcome in outcomes)])


def main() -> int:
    parser = argparse.ArgumentParser(prog="kb_evals.bakeoff")
    parser.add_argument("--dense", nargs="+", default=list(DENSE_MODELS))
    parser.add_argument("--sparse", nargs="+", default=list(SPARSE_MODELS))
    parser.add_argument(
        "--rerank",
        nargs="+",
        default=[name or "none" for name in RERANK_MODELS],
        help="model names, or none for no reranker",
    )
    args = parser.parse_args()
    rerank = [None if name == "none" else name for name in args.rerank]
    warnings.filterwarnings("ignore", message="Payload indexes have no effect")
    print(_HEADER, flush=True)
    outcomes = asyncio.run(_bakeoff(args.dense, args.sparse, rerank))
    print()
    print(format_table(outcomes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
