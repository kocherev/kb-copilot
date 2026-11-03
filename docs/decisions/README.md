# Decisions

One file per architecture decision, with its context, the decision, and its consequences.

| File | Status | Decides |
| --- | --- | --- |
| `0001-retrieval.md` | Accepted | Hybrid search in one Qdrant collection with FastEmbed `google/embeddinggemma-300m` dense vectors and `Qdrant/bm25` sparse vectors, rank fusion, and abstention on a dense-score threshold. No reranker by default, with the bakeoff that shows why. |
| `0002-evals.md` | Accepted | The 46-page sample corpus, the 152-row dataset, the offline gate and its held-out split, and the four live judges. |
| `0003-voice-model.md` | Accepted | One Gemini Live model through the LiveKit Google plugin on any LiveKit host, screen frames as video input, citations as data messages, and a worker that never starts silently. |
| `0004-desktop-actions.md` | Accepted | A macOS helper that performs approved actions over LiveKit RPC, planned to be driven by a Computer Use tool in the agent. The agent tool and the approval step are not built yet. |
