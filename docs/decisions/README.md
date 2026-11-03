# Decisions

One file per architecture decision, with its context, the decision, and its consequences. [docs/design.md](../design.md) shows how they fit together.

| File | Status | Decides |
| --- | --- | --- |
| [0001-retrieval.md](0001-retrieval.md) | Accepted, 2026-11-02 | Hybrid search in one Qdrant collection with FastEmbed `google/embeddinggemma-300m` dense vectors and `Qdrant/bm25` sparse vectors, rank fusion, and abstention on a dense-score threshold. No reranker by default, with the bakeoff that shows why. |
| [0002-evals.md](0002-evals.md) | Accepted, 2026-11-02 | The 46-page sample corpus, the 152-row dataset, the offline gate and its held-out split, and the four live judges. Judge v2 and the dated live results, 2026-11-03. |
| [0003-voice-model.md](0003-voice-model.md) | Accepted, 2026-11-02 | One Gemini Live model through the LiveKit Google plugin on any LiveKit host, screen frames as video input, citations as data messages, a worker that never starts silently, and the agent's name and voice per product. |
| [0004-desktop-actions.md](0004-desktop-actions.md) | Accepted | A macOS helper that sends screenshots, draws the agent's cursor, and performs actions over LiveKit RPC. The agent's `operate_computer` tool plans each step with Gemini Computer Use, and the user approves every step in the page. The 2026-11-03 addendum covers the approval loop, screenshots, and the cursor on the real screen. |
| [0005-linear-handoff.md](0005-linear-handoff.md) | Accepted, 2026-11-02 | Handoff to a person as a Linear issue. OAuth instead of a personal key, signed single-use state, encrypted tokens, an issue created only after the user approves, redaction, and the retry of an approval stuck in `creating`. |
| [0006-lean-runtime.md](0006-lean-runtime.md) | Accepted, 2026-11-03 | The API owns the embedding models, the agent searches and checks citations through it, citations embed only the answer, and indexing is capped to one text at a time and 2 threads. The citation word matching revised on 2026-11-03. |
| [0007-session-replay.md](0007-session-replay.md) | Accepted, 2026-11-03 | A `turns` table, an agent that posts each turn without blocking the voice loop, a Sessions list and a replay page with a latency bar per turn, redaction and retention, and OpenTelemetry export that is off unless an endpoint is set. |
