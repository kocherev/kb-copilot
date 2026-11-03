import argparse
import asyncio
import warnings

from kb_evals.bakeoff import HASH_BASELINE, retriever_for
from kb_evals.run import (
    DATASET_PATH,
    DOCS_PATH,
    THRESHOLDS_PATH,
    exit_code,
    format_report,
    run_eval,
)


def main() -> int:
    parser = argparse.ArgumentParser(prog="kb_evals")
    parser.add_argument(
        "--config",
        default="default",
        help=f"default (kb_rag settings) or {HASH_BASELINE}",
    )
    args = parser.parse_args()
    warnings.filterwarnings("ignore", message="Payload indexes have no effect")
    report = asyncio.run(
        run_eval(retriever_for(args.config), DOCS_PATH, DATASET_PATH, THRESHOLDS_PATH)
    )
    print(format_report(report))
    return exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
