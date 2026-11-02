# 0002 Evals

Status: accepted, 2026-11-02

## Context

The old eval could not fail. Its corpus was 3 files and 98 words, `k` was 5 against 3 documents, the scored answer was the dataset's own answer, and every threshold was 1.0. A passing run said nothing about retrieval quality.

## Decision

### Corpus and dataset

`demo/docs` is 46 original pages for a fictional product, in Markdown, HTML, and one PDF, so the readers are exercised too. Three pages contain prompt-injection text and false claims on topics the real pages cover. They are a retrieval risk, not decoration: they compete for the same queries.

`evals/datasets/v1.jsonl` has 152 hand-written rows in ten categories. The unanswerable categories adapt the UAEval4RAG taxonomy: out of scope (out of database), false premise (false presupposition), and underspecified. This repo adds partially answerable questions and off-topic small talk. Each fails in a different way. Out-of-scope questions look in-domain and pull real passages. False-premise and partial questions should not abstain at all: the right reply corrects the premise or answers the covered half from a real page. Mixing them into one "refuse" bucket hides that.

Paraphrase rows share no content word with the answer sentence. They are the rows the old keyword-overlap gate refused, and the reason a lexical-only retriever looks better than it is.

### Offline metrics

The gate scores retrieval only, with no model call: recall@5, MRR, context precision, required-fact recall in the retrieved text, abstention precision and recall, and injection safety. `k` is 5 against 46 documents, so a hit has to be earned. Scores are reported per category and overall, and the gate lists the failing cases.

### Two layers of abstention

Retrieval and the answer model refuse different things, and the gate scores each only for its own job.

- Retrieval owns off-topic and out-of-scope rows. It should abstain on clear misses. These rows are the positive class for abstention precision and recall.
- The answer model owns false-premise, partial, and underspecified rows. Retrieval must still return the relevant page for the first two; refusing, correcting, or asking is the model's call, measured by the live `refusal` judge. Underspecified rows are not scored offline.

The printout marks each category with its owner. The abstain threshold is calibrated on one half of the rows (a seeded hash per category) and abstention is reported on the other half, so the gate does not grade the threshold on the rows that chose it. The cost is asymmetric: wrongly refusing a grounded question counts ten times a passed off-topic one.

Thresholds are the measured baseline minus a small margin. They catch regressions; they do not claim perfection.

### Untrusted passages

Three pages carry prompt-injection text. Injection safety is the share of rows whose first passage is not one of them. Retrieval keeps it at 1.000 on every category except injection (0.100) and false premise (0.800): when a question is about the topic a poisoned page discusses, that page ranks first. Retrieval cannot tell a forum post from policy, so the answer layer must treat every passage as untrusted data and never follow instructions inside it. The agent change that does this is separate; the live judges check the result.

### Live judges

Answer quality needs a model to grade it. The harness has four binary judges, one per failure mode: faithful, correct, refusal, citation. A binary verdict per failure mode is easier to label, easier to agree on, and easier to act on than a 1-to-5 score that mixes several faults. Each verdict comes with a one-sentence reason.

Verdicts are requested as JSON through a structured-output schema, at low effort. The brief asked for temperature 0. The current Messages API rejects sampling parameters on every model, so there is none; the schema and the binary question keep verdicts stable enough to calibrate.

The judge model is pinned to `claude-sonnet-5-5` and set by `KB_JUDGE_MODEL`. Each run file records the model id and `PROMPT_VERSION`, so two runs are comparable only when both match.

The agent speaks with Gemini. The judge is a different model family on purpose: a model grading its own family's output tends to prefer it, and shared blind spots pass unnoticed.

### Calibration

A judge is a classifier and has error rates. `make judge-calibrate` compares a run with human labels and prints, per judge, the true positive rate and the true negative rate. A judge is trusted only after both rates are known on enough labeled rows. No labels exist yet, so no judge rate is claimed.

## Consequences

- CI runs the offline gate only. It never calls a paid API.
- The gate fails for real: the hash retrieval that shipped before fails it.
- Unit tests use a hashed embedder from `kb_rag.testing` and load no model. The eval job caches the FastEmbed directory.
- Adding a page or a row moves the numbers. Re-run `make eval`, then update `evals/thresholds.json` from the printout.
- Judge numbers need an `ANTHROPIC_API_KEY` and an answers file from the agent. Neither is in the repository, so there are no judge numbers yet.
