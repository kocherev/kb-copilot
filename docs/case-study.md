# Case study

Three problems found while building kb-copilot, with the cause, the fix, and the numbers before and after. Every number here comes from a merged pull request or a decision record, linked in each section.

## 1. The live eval measured the harness, not the agent

Sources: [#40](https://github.com/kocherev/kb-copilot/pull/40), [0002](decisions/0002-evals.md), [0006](decisions/0006-lean-runtime.md).

### What broke

The first live run had Gemini `gemini-3.8-flash` answer all 152 eval questions with the agent's prompt and tools, and `claude-haiku-5-5` judge each answer four ways. The scores were low. Citation was the worst at 0.388, with 94 of 152 answers citing nothing. Reading the verdicts showed that many failures came from the measurement rather than the answers.

### Root causes

- The judges graded against their own search. Each judge ran a fresh search for the question and graded against its top five passages. Gemini often searched with other words. Four answers cited passages outside that top five and were graded as citing nothing.
- The refusal judge could not see the passages. It failed answers it had no way to check. Of its 39 failures on rows that should be answered, 21 gave that reason.
- Every eval row was the first turn of a conversation, so every answer opened with a greeting, and the refusal judge failed refusals that were not the bare sentence.
- Spoken filler broke citation matching. A passage is cited when an answer sentence is close to it and 90% of the sentence's content words appear in it. Of the 117 answers to a question with a source, 54 had a sentence close enough that failed the word check. The missing words were filler a speaker adds ("your", "from", "when", "then", "they") or a plural ("requests" against "request"). In a six-word sentence one such word is 17% of it.
- The tool stubs were missing. The prompt names `handoff_to_human`, and the answer generator did not register it, so the run crashed when Gemini called it.

### Fix

- The answers file records every passage the model's searches returned, and the judges read those.
- The refusal judge sees the passages and grades only the choice: answer, refuse, correct, ask, or answer the covered part.
- Each conversation opens with the agent's greeting as a model turn, as a live session does.
- The citation word check skips a short list of filler words and drops a plural "s", on both sides. Negations still count. The cutoffs did not change.
- Every agent tool has a stub that returns what production returns when there is nothing to act on, and a test fails when a tool has none.

Then, separately, the agent's prompt changed: answer the covered part and name the gap, correct a false premise, ask when a question is vague, refuse general knowledge, ignore instructions in the user's message, trust product pages over forum posts, and propose a handoff only after the user agrees.

### Before and after

152 rows, pass rate per judge:

| Run | Faithful | Correct | Refusal | Citation | Answers with no citation |
| --- | --- | --- | --- | --- | --- |
| Before (judge v1) | 0.776 | 0.816 | 0.579 | 0.388 | 94 |
| Measurement fixed (judge v2) | 0.928 | 0.822 | 0.836 | 0.553 | 77 |
| Prompt fixed | 0.954 | 0.895 | 0.908 | 0.671 | 68 |

The second row's gain comes from the harness, the judges and the citation rule, not from how the agent answers. Its prompt differs from the first run's only by the computer-use tool, which was added in between. The third row changes only the prompt.

The citation rule on its own, re-scored on the 117 rows with a source, against the 152 answers of the first run:

| Rule | Live precision | Live recall | Live answers with a citation | Gold precision |
| --- | --- | --- | --- | --- |
| Before | 79.0% | 33.6% | 54 of 117 | 94.0% |
| After | 82.5% | 44.5% | 70 of 117 | 92.5% |

### What it does not prove

Each row is one run with no repeat. The judges are not yet calibrated against human labels, so their error rates are unknown, and a difference of one or two rows in a category is noise. `make judge-calibrate` is built and waiting for labels. Version 1 and version 2 judge numbers are not comparable with each other.

## 2. The runtime did not fit on a laptop

Source: [0006](decisions/0006-lean-runtime.md).

### What broke

The stack has to run on a 16 GB MacBook with an 8 GB, 8 CPU Docker VM. Voice sessions stuttered, and indexing a large upload killed the API.

### Root causes

- Every voice session started an agent process that loaded the 300M-parameter dense model again on its first search, about 0.8 GB, while the API held its own copy.
- After every answer the agent embedded each sentence of every retrieved passage, dozens of sentences on a busy CPU while audio streamed.
- Indexing embedded a whole file in one batch of 256 texts. Each text is padded to the longest one, so a 600 KB file used 7.3 GB. The VM killed the API, Compose restarted it, the queue handed it the same job, and it died again.
- Indexing used every core, and LiveKit kept one warm job process per CPU, 8 of them, while no one was in a session.

### Fix

- The API owns the embedding models. The agent calls `POST /internal/search` and `POST /internal/citations` and loads no model.
- A citation embeds only the answer's sentences and compares each passage by the dense vector the index already stores.
- Indexing embeds one text at a time, with `KB_EMBED_THREADS` (2 in Compose) ONNX threads.
- The worker keeps one warm job process instead of one per CPU.

### Before and after

Measured on a Mac with a Docker VM of 8 CPUs and 8 GB, 40 eval questions against the same index. The machine was running other work, so read the times as rough.

| | Before | After |
| --- | --- | --- |
| Agent process memory after the first search | 926 MB | 209 MB |
| Agent process memory, peak | 1.02 GB | 209 MB |
| First `search_kb` of a session | 1.7 to 7.4 s | 0.1 s |
| Citation check per turn, median | 440 to 547 ms | 34 ms |
| Citation check per turn, p95 | 676 to 764 ms | 50 ms |
| Agent container with no session running | 1.12 GiB | 0.60 GiB |
| Indexing 19 files (1.7 MB) | API killed at 7.3 GB, restart loop | 2,475 chunks in 11.7 min, 1.5 GB peak, no restart |

The extra hop through the API costs 1.1 ms at the median. With two threads, indexing does the same CPU work as with one in half the wall time (56 s against 127 s for 197 chunks), while eight threads took 58 s and nearly four times the CPU.

The cheaper citation rule had a cost too. On the gold answers its recall was 0.7 points lower and its precision 3.5 points higher than the sentence-against-sentence rule it replaced. `make eval` printed the same table before and after.

## 3. The smoke job failed after it passed

Source: [#41](https://github.com/kocherev/kb-copilot/pull/41).

### What broke

The CI smoke job brings up the Compose stack with LiveKit and walks the quickstart: sign-up, a product, an upload, a session, and the agent's first reaction in the room. It sometimes exited with code 134 right after printing `smoke passed`. It happened on `main` twice and on one pull request.

### Root cause

The LiveKit SDK's native runtime panicked while the Python interpreter shut down ("panic in a function that cannot unwind"). By then the test had passed and the room was disconnected, so nothing was left to clean up.

### Fix

`scripts/smoke.py` flushes stdout and calls `os._exit` after `main()` returns, so the interpreter's shutdown never runs. A failure still raises `SystemExit` inside `main()`, so it keeps its message and a non-zero exit code.

### What it does not prove

One green run cannot show that a flake is gone. If exit 134 comes back, the cause is somewhere else.
