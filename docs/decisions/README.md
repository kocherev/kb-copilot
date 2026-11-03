# Decisions

One file per architecture decision, with its context, the decision, and its consequences.

| File | Status | Decides |
| --- | --- | --- |
| `0001-retrieval.md` | Accepted | Hybrid search in one Qdrant collection with FastEmbed `google/embeddinggemma-300m` dense vectors and `Qdrant/bm25` sparse vectors, rank fusion, and abstention on a dense-score threshold. No reranker by default, with the bakeoff that shows why. |
| `0002-evals.md` | Accepted | The 46-page sample corpus, the 152-row dataset, the offline gate and its held-out split, and the four live judges. |
| `0003-voice-model.md` | Accepted | One Gemini Live model through the LiveKit Google plugin on any LiveKit host, screen frames as video input, citations as data messages, and a worker that never starts silently. |
| `0004-desktop-actions.md` | Accepted | A macOS helper that sends screenshots, draws the agent's cursor, and performs actions over LiveKit RPC. The agent's `operate_computer` tool plans each step with Gemini Computer Use, and the user approves every step in the page. |
| `0006-lean-runtime.md` | Accepted | The API owns the embedding models, the agent searches and checks citations through it, citations embed only the answer, and indexing is capped to one text at a time and 2 threads. |
| `0007-session-replay.md` | Accepted | A `turns` table, an agent that posts each turn without blocking the voice loop, a Sessions list and a replay page with a latency bar per turn, redaction and retention, and OpenTelemetry export that is off unless an endpoint is set. |
