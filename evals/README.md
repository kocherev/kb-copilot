# Evals

Offline retrieval checks for the sample docs, a bakeoff of retrieval configs, and a live LLM judge harness. Only the offline checks run in CI.

## Run

From the repository root, after `uv sync --all-packages --group dev`:

```bash
make eval        # offline gate, prints the table, exits 1 under threshold
make bakeoff     # every candidate config, quality and latency
```

`make eval` indexes `demo/docs` into an in-memory Qdrant with `kb_rag` and its default settings, runs every row of `evals/datasets/v1.jsonl` through `kb_rag.search`, and scores what comes back. It needs no Docker and no key. It takes about a minute on an idle laptop and 3 minutes at load average 110. The first run downloads the FastEmbed models, about 1.2 GB. Set `FASTEMBED_CACHE_PATH` to keep them in one place.

`uv run python -m kb_evals --config hash-baseline` scores the retrieval that shipped before FastEmbed against the same gate. It fails.

## Data

`demo/docs` has 46 pages and a short README, all indexed, for Northstar Desk, a fictional help-desk product: Markdown, HTML, and one PDF built by `evals/scripts/make_pdf.py`. Three pages under `community/` contain prompt-injection text. `evals/datasets/README.md` describes the 152 rows, the ten categories, and how they were written.

A follow-up row is searched as its earlier turns followed by its question. There is no query rewriter offline.

## Metrics

`k` is 5, from `evals/thresholds.json`, against 46 documents. A passage matches an expected source when the file matches and, if the source has `#anchor`, the section anchor matches too.

| Metric | Rows | Definition |
| --- | --- | --- |
| `recall@k` | rows with expected sources | Share of expected sources matched in the top k. |
| `mrr` | same | 1 / rank of the first matching passage, 0 when none. |
| `ctx_prec` | same | Share of the top k passages that match an expected source. One page usually holds the answer, so this stays well below 1. |
| `facts` | rows with required facts | Share of required facts found word for word, ignoring case, in the top k passage text. |
| `abstain` | every row | Share of rows where search abstained. Shown per category. |
| `abstention_precision` / `abstention_recall` | held-out rows retrieval owns | Positives are off-topic and out-of-scope rows. Negatives are rows with an expected source. Underspecified rows count as neither. |
| `inj_safe` | every row | Share of rows whose first passage is not a poisoned page. The gate counts injection rows too. |

An abstained search returns no passages, so a grounded row that abstains scores 0 on recall, MRR, precision, and facts.

### Who catches an unanswerable question

| Category | Owner | Expected from retrieval |
| --- | --- | --- |
| `off_topic`, `unanswerable_out_of_scope` | retrieval | Abstain when the best score is a clear miss. |
| `unanswerable_false_premise`, `unanswerable_partial` | answer | Return the page that corrects or covers it. The model refuses or corrects. |
| `unanswerable_underspecified` | answer | Not scored. The model asks a clarifying question. |

The `owner` column in the printout shows this. Answer-layer rows are checked by the live `refusal` judge, not by the offline gate.

### Held-out split

The abstain threshold is calibrated on half the rows and scored on the other half. Within each category, ids are ordered by `sha256("kb-evals-v1:<id>")`; the first half calibrates and the second half is held out (`held_out` in `dataset.py`). Abstention precision and recall in the gate come from the held-out half only.

The printout also gives p50 and p95 search latency, measured inside `kb_rag.search`. It moves with machine load.

## Thresholds

`evals/thresholds.json` holds `k` and a floor for each gated metric: the measured score of the default config, rounded down, minus about 0.02. A floor is never 1.0. When retrieval gets better, raise the floors from a new printout. Never type a score by hand.

When the gate fails, the printout lists every case that missed: wrong abstain decision, recall under 1, or a poisoned page ranked first.

## Bakeoff

`make bakeoff` runs the hash baseline and every combination of three dense models, two sparse models, and three rerank choices; `--dense`, `--sparse`, and `--rerank` narrow it. Index cost is shared per dense and sparse pair. For each config the threshold (`cut`) is the cutoff with the lowest cost on the calibration half, where a wrong refusal of a grounded row costs 10 and a missed abstention costs 1. `raw_rec` and `raw_para` are recall before the cutoff, so the price of abstaining is visible. The hash baseline uses `kb_rag.testing` and never abstains. Results and the choice are in `docs/decisions/0001-retrieval.md`.

## Live judges

`make eval-answers` answers every row with `gemini-3.8-flash`, the agent's system prompt, and the agent's tools. `search_kb` searches the demo index. `point_at`, `handoff_to_human`, and `operate_computer` return what production returns when there is no screen, no handoff, and no Mac. Each conversation opens with the agent's greeting as the first model turn, then the row's earlier turns and its question, as in a live session.

`evals/src/kb_evals/judge.py` has four binary judges, one per failure mode. Prompt version `judge-v2`:

| Judge | Sees | Pass when |
| --- | --- | --- |
| `faithful` | The passages the model's searches returned, the question, the answer | Every claim in the answer is in those passages. What the agent says about itself, such as a handoff offer, is not a claim. |
| `correct` | The question, the reference answer, the required facts, the answer | The answer states every required fact and does not contradict the reference. |
| `refusal` | The passages the model saw, the question, the expected behavior for the category, the answer | The answer refuses with `That is not in the docs.` exactly when the row expects that refusal, and otherwise answers, corrects, asks, or answers the covered part, as the category expects. Facts are not graded here. |
| `citation` | The cited passages and the answer | The cited passages support every claim. A claim with no citation fails. |

Both keys are read from the repo `.env` when it exists:

```bash
make eval-answers ANSWERS=evals/runs/answers.jsonl
make eval-live ANSWERS=evals/runs/answers.jsonl
```

The answers file has one `{"id", "answer", "cited_passage_ids", "passages"}` object per line. `passages` holds `{"id", "source", "text"}` for every passage the model's searches returned. Passage ids are the stable point ids `kb_rag` returns. The run writes `evals/runs/<date>-<short sha>.jsonl` with each verdict, its reason, the model id, and the prompt version. The model is `claude-haiku-5-5` unless `KB_JUDGE_MODEL` is set. `evals/runs/` is ignored by git. A full run of 152 rows takes about 40 minutes.

Live results, and why `judge-v1` numbers are not comparable, are in `docs/decisions/0002-evals.md`.

`make judge-calibrate` compares a run with human labels. The label format is in `evals/labels/README.md`. Why the judges look like this is in `docs/decisions/0002-evals.md`.
