# 0006 Lean runtime

Status: accepted, 2026-11-03

## Context

The stack has to run on a 16 GB MacBook with an 8 GB, 8 CPU Docker VM. Five things made it stutter or fall over:

1. After every assistant message the agent embedded each sentence of every retrieved passage plus the answer. That is dozens of sentences on a loaded CPU while Gemini Live audio streams.
2. The agent and the API each loaded the 300M-parameter dense model (about 0.8 GB each), and every voice session started a new agent process that loaded it again on its first search.
3. Indexing embedded a whole file in one batch of 256 texts. Each text is padded to the longest, so a 600 KB file used 7.3 GB. The VM killed the API, `restart: unless-stopped` brought it back, the queue requeued the job, and it died again.
4. Indexing used every core.
5. LiveKit keeps one warm job process per CPU, so the agent container held 8 of them, 1.1 GiB, while nobody was in a session.

## Decision

- The API owns the embedding models. It loads them at start. The agent calls two routes with `X-Internal-Token`: `POST /internal/search` (`product_id`, `query`, `limit`) and `POST /internal/citations` (`product_id`, `answer`, `passage_ids`). The agent keeps one `httpx` client per session, with a 5 s timeout. The routes are not in the OpenAPI schema, because the browser never calls them. The agent no longer loads a model, reads Qdrant, or mounts the model cache.
- A citation embeds only the answer's sentences, normally one to four. Each retrieved passage is compared by the dense vector the index already stores for it.
- Indexing embeds one text at a time, and `KB_EMBED_THREADS` caps the ONNX threads. Compose sets 2.
- The worker keeps one warm job process (`num_idle_processes=1`) instead of one per CPU.
- `services/mcp` still uses `kb_rag` in its own process, as before.

### Citation rule

A stored vector covers a whole passage (up to 120 words), so a sentence scores lower against it than against a sentence of that passage. Cosine alone lost most of the recall at the old precision:

| Rule, gold answers of the 116 eval rows with a source, top five passages | Precision | Recall | Cited per answer |
| --- | --- | --- | --- |
| Before: sentence against sentence at 0.8 | 90.5% | 47.6% | 0.91 |
| Cosine to the passage vector only, at 0.80 | 89.8% | 24.8% | 0.42 |
| Cosine only, at 0.70 | 87.8% | 39.3% | 0.84 |
| After: cosine at least 0.85, or at least 0.55 with 90% of the sentence's content words in the passage | 94.0% | 46.9% | 0.86 |

Precision is the share of cited passages from a page the dataset expects. Recall is the share of expected sections cited. The three cutoffs are in `packages/rag/src/kb_rag/citations.py`. They were picked on the same 116 rows they are scored on, so treat the table as a guide. The gold answers are close to the passages' wording, which helps the word-overlap check more than a spoken paraphrase would. `make eval-answers` then `make eval-live` judges real model answers.

### Threads and batch size

Indexing 197 chunks of three files on the host, one text per batch:

| Threads | Wall | CPU seconds |
| --- | --- | --- |
| 1 | 127 s | 102 |
| 2 | 56 s | 102 |
| 3 | 40 s | 114 |
| 4 | 34 s | 131 |
| 8 | 58 s | 381 |

Two threads do the same work as one in half the time and leave six cores free. Eight oversubscribe and burn four times the CPU. Embedding one text at a time used about 1.0 GB, against 1.5 GB at a batch of 8, 2.4 GB at 32, and 7.8 GB at the default 256, and it used the least CPU. A query embeds in 20 ms with every core and 31 ms with two. During indexing the search route answered in a median of 37 ms (21 ms idle).

## Measured

Mac with 8 cores and a Docker VM of 8 CPUs and 8 GB. The agent numbers are from `docker compose run` of the agent image, 40 eval questions, against the same index. The machine also ran other work (load average 4 to 14), so read the times as rough.

| | Before | After |
| --- | --- | --- |
| Agent process memory, after imports | 205 MB | 209 MB |
| Agent process memory, after the first search | 926 MB | 209 MB |
| Agent process memory, peak | 1.02 GB | 209 MB |
| First `search_kb` of a session | 1.7 to 7.4 s | 0.1 s |
| `search_kb`, median | 32 to 38 ms in process | 23 ms through the API |
| Added hop, median | none | 1.1 ms |
| Citation check per turn, median / p95 | 440 to 547 ms / 676 to 764 ms | 34 ms / 50 ms |
| Agent container memory, no session running | 1.12 GiB (8 warm processes) | 0.60 GiB (1 warm process) |
| API memory, models loaded | 1.0 to 1.4 GB | 1.2 GB |
| Indexing the 19 files of `kb-demo-claude-code` (1.7 MB) | API killed at 7.3 GB, restart loop | 2,475 chunks in 11.7 min, API 205% CPU on average, 1.5 GB peak, no restart |
| Same files on the host without `errors.md`, one process | 1,633 chunks, 6,245 s, 8,495 CPU s, 7.8 GB peak, swapping | not rerun |

The image sizes did not change: the agent still imports `kb_rag` for `NOT_IN_DOCS` (see below), which pulls in fastembed.

`make eval` prints the same table before and after, including every gated score.

## Consequences

- One model copy serves search, indexing and citations, however many sessions run.
- The API is now on the path of every search. If it is down the tool fails, as it did when Qdrant was down. The API warms its models at start (`WARM_MODELS=false` turns that off), so a restart costs a few seconds for the first search.
- A second session that starts while another is starting waits for a new job process, about 2.5 s here.
- Citation recall is 0.7 points lower on the eval rows and precision is 3.5 points higher. Live answers may paraphrase more than gold answers do.
- With `KB_EMBED_THREADS` unset, which is the case for commands on the host such as `make eval`, onnxruntime uses every core.
- Not done: `services/agent/src/kb_agent/prompt.py` still has `from kb_rag import NOT_IN_DOCS`. Moving that constant into the agent would let the agent drop `kb-rag` (a dev dependency would still serve `selfcheck` and the tests), which removes about 60 MB per agent process and the model libraries from the image.
