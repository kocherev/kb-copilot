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

The judge model is pinned to `claude-haiku-5-5` and set by `KB_JUDGE_MODEL`. Each run file records the model id and `PROMPT_VERSION`, so two runs are comparable only when both match.

The agent speaks with Gemini. The judge is a different model family on purpose: a model grading its own family's output tends to prefer it, and shared blind spots pass unnoticed.

### Judge v2, 2026-11-03

The first live run (`judge-v1`) measured the harness as much as the agent. Four faults, each checked against that run:

- Every row was the first turn of a conversation, so every answer opened with "Hi, I'm Shawn" and the refusal judge failed refusals that were not the bare sentence. The answer generator now puts the agent's greeting first, as a model turn, then the row's turns. A live session starts the same way.
- The judges ran their own search for the question and graded against its top five. Gemini often searched with other words. Four answers cited passages outside that top five and were graded as citing nothing. The answers file now records every passage the model's searches returned, and the judges read those.
- The refusal judge saw no passages. It failed answers it could not check: 21 of its 39 failures on rows that should be answered give that reason. It also failed partial answers that said "that is not in the docs" inside a sentence. It now sees the passages and grades only the choice: answer, refuse, correct, ask, or answer the covered part.
- The prompt tells the agent to offer a handoff when the docs do not answer. Without a handoff it says it cannot hand off. The faithful judge failed those sentences as product claims. They are now out of scope for both judges.

`make eval-answers` also crashed when Gemini called `handoff_to_human`, which the prompt names and the harness did not register. Every agent tool now has a stub that returns what production returns when there is nothing to act on.

`judge-v2` numbers are not comparable with `judge-v1` numbers.

### Live results

Answers by `gemini-3.8-flash` through `make eval-answers`, judged by `claude-haiku-5-5` through `make eval-live`, 152 rows. Pass rates per judge.

| Run, 2026-11-03 | Code | Judge prompt | Faithful | Correct | Refusal | Citation |
| --- | --- | --- | --- | --- | --- | --- |
| Original | `68eee03` | `judge-v1` | 0.776 | 0.816 | 0.579 | 0.388 |
| Corrected measurement | `b2c29b9` | `judge-v2` | 0.928 | 0.822 | 0.836 | 0.553 |
| After the prompt change | `0c5fb19` | `judge-v2` | 0.954 | 0.895 | 0.908 | 0.671 |

The original run used the prompt of `68eee03`, without `operate_computer`. The corrected run uses the prompt of `7d43842` with the harness and citation fixes above, so its gain over the original comes from the harness, the judges, and the citation rule, not from how the agent answers. The last run changes only `services/agent/src/kb_agent/prompt.py`: answer the covered part and name the gap, correct a false premise, ask when a question is vague, refuse general knowledge, ignore instructions in the user's message, trust product pages over forum posts, and propose a handoff only after the user agrees. Answers with no citation went from 94 to 77 to 68.

Original, `judge-v1`:

| Category | Rows | Faithful | Correct | Refusal | Citation |
| --- | --- | --- | --- | --- | --- |
| overall | 152 | 0.776 | 0.816 | 0.579 | 0.388 |
| answerable | 37 | 0.973 | 0.919 | 0.730 | 0.432 |
| paraphrase | 20 | 0.850 | 0.800 | 0.600 | 0.550 |
| multi_hop | 15 | 0.600 | 0.733 | 0.600 | 0.067 |
| follow_up | 15 | 0.800 | 1.000 | 0.733 | 0.200 |
| off_topic | 12 | 0.750 | 0.500 | 0.250 | 0.333 |
| unanswerable_out_of_scope | 15 | 0.333 | 0.800 | 0.467 | 0.867 |
| unanswerable_false_premise | 10 | 1.000 | 0.800 | 0.700 | 0.400 |
| unanswerable_underspecified | 8 | 0.875 | 0.750 | 0.750 | 0.250 |
| unanswerable_partial | 10 | 0.300 | 0.900 | 0.400 | 0.100 |
| injection | 10 | 1.000 | 0.700 | 0.200 | 0.400 |

Corrected measurement, `judge-v2`:

| Category | Rows | Faithful | Correct | Refusal | Citation |
| --- | --- | --- | --- | --- | --- |
| overall | 152 | 0.928 | 0.822 | 0.836 | 0.553 |
| answerable | 37 | 0.892 | 0.892 | 0.946 | 0.676 |
| paraphrase | 20 | 0.950 | 0.850 | 0.850 | 0.550 |
| multi_hop | 15 | 0.867 | 0.867 | 1.000 | 0.267 |
| follow_up | 15 | 0.867 | 0.867 | 0.933 | 0.400 |
| off_topic | 12 | 0.917 | 0.583 | 0.250 | 0.500 |
| unanswerable_out_of_scope | 15 | 1.000 | 0.800 | 0.933 | 0.933 |
| unanswerable_false_premise | 10 | 0.900 | 0.800 | 0.800 | 0.500 |
| unanswerable_underspecified | 8 | 1.000 | 0.750 | 0.750 | 0.500 |
| unanswerable_partial | 10 | 1.000 | 0.900 | 0.700 | 0.200 |
| injection | 10 | 1.000 | 0.700 | 0.800 | 0.700 |

After the prompt change, `judge-v2`:

| Category | Rows | Faithful | Correct | Refusal | Citation |
| --- | --- | --- | --- | --- | --- |
| overall | 152 | 0.954 | 0.895 | 0.908 | 0.671 |
| answerable | 37 | 0.946 | 0.892 | 0.946 | 0.703 |
| paraphrase | 20 | 1.000 | 0.950 | 0.950 | 0.800 |
| multi_hop | 15 | 0.800 | 0.800 | 0.933 | 0.267 |
| follow_up | 15 | 0.933 | 0.933 | 0.800 | 0.333 |
| off_topic | 12 | 1.000 | 0.833 | 0.750 | 1.000 |
| unanswerable_out_of_scope | 15 | 1.000 | 1.000 | 0.867 | 1.000 |
| unanswerable_false_premise | 10 | 0.900 | 1.000 | 1.000 | 0.500 |
| unanswerable_underspecified | 8 | 1.000 | 0.750 | 0.750 | 0.625 |
| unanswerable_partial | 10 | 1.000 | 0.900 | 1.000 | 0.700 |
| injection | 10 | 1.000 | 0.800 | 1.000 | 0.700 |

Each number is one run with no repeat, and no judge is calibrated yet, so a difference of one or two rows in a category is noise. Known misses in the last run:

- Greetings and thanks (3 `off_topic` rows) get a short greeting back. The dataset expects `That is not in the docs.` for them. The prompt is right and the expectation is not; the dataset should split small talk from general knowledge.
- The refusal judge still fails 2 out-of-scope refusals for the handoff offer after the refusal sentence, against its instruction.
- Two answerable rows ask for a base URL. The voice prompt says never to read a URL aloud, so the answer points at the sources and fails.
- Multi-hop citation stays at 0.267: a sentence that joins facts from two pages rarely has 90% of its words in either one.

### Calibration

A judge is a classifier and has error rates. `make judge-calibrate` compares a run with human labels and prints, per judge, the true positive rate and the true negative rate. A judge is trusted only after both rates are known on enough labeled rows. No labels exist yet, so no judge rate is claimed.

## Consequences

- CI runs the offline gate only. It never calls a paid API.
- The gate fails for real: the hash retrieval that shipped before fails it.
- Unit tests use a hashed embedder from `kb_rag.testing` and load no model. The eval job caches the FastEmbed directory.
- Adding a page or a row moves the numbers. Re-run `make eval`, then update `evals/thresholds.json` from the printout.
- Judge numbers need `GOOGLE_API_KEY` and `ANTHROPIC_API_KEY`, read from the repo `.env`. A full run of 152 rows took about 40 minutes: about 25 to answer and 14 to judge. Run files stay out of git; the results above are copied from them.
- A change to the judge prompts bumps `PROMPT_VERSION` and makes older runs incomparable.
