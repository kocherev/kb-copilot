# 0001 Retrieval

Status: accepted, 2026-11-02. Revised the same day: no reranker on the hot path.

## Context

Retrieval used a sha256 token hash as the "dense" vector and hashed raw counts as the sparse vector. A keyword-overlap gate in the agent decided refusals. On the old demo it refused "How quickly will I get my money back?", refused small talk, and let 5 of 6 in-domain unanswerable questions through. Stored sources were absolute file URIs, which leaked local paths to the browser.

The agent is a voice agent. A spoken turn has about one second before the pause feels broken, and retrieval runs inside that turn, before the model speaks.

## Decision

`packages/rag` owns retrieval end to end:

- Heading-aware chunks. Each chunk keeps its nearest heading as `title` and the heading slug as `anchor`. HTML h1 to h3 count as headings.
- One Qdrant collection, `kb_chunks`, with a dense vector, a sparse vector with the IDF modifier, and a tenant keyword index on `product_id`. It is created once, not checked on every search.
- Stable point ids per product, source, and chunk. Re-indexing a source upserts first, then deletes the chunks it no longer has.
- A source is a path relative to the ingest root, or `upload://name`. An absolute path or a `file:` URI is rejected.
- `search` runs dense and sparse prefetch, fuses them with RRF, and scores each passage by its dense cosine similarity to the query. It abstains when the best score is under `abstain_threshold`. An abstained result has no passages.
- A cross-encoder reranker is an opt-in setting (`reranker`), off by default.
- Embedders are objects in `RetrievalSettings`. FastEmbed models load once per process. Tests pass the hashed embedder in `kb_rag.testing` and download nothing.

Defaults, in `RetrievalSettings`:

| Setting | Value |
| --- | --- |
| `dense` | FastEmbed `google/embeddinggemma-300m` |
| `sparse` | FastEmbed `Qdrant/bm25` |
| `reranker` | none |
| `abstain_threshold` | `0.379` (dense cosine) |
| `candidates` | 20 (only used with a reranker) |

### Two layers of abstention

Retrieval abstains only on clear misses: off-topic chat and out-of-scope questions whose best passage is far from the query. False-premise, partially answerable, and underspecified questions do have relevant passages; the answer model decides with those passages in front of it, and the live `refusal` judge measures it (see `0002-evals.md`).

The threshold is the cutoff with the lowest cost on a calibration half of the dataset, where wrongly refusing a grounded question costs 10 and passing an off-topic one to the model costs 1. A wrong refusal loses an answer the docs have and cannot be recovered; a passed off-topic question still reaches a model that can refuse.

## Bakeoff

### First pass: with a reranker

`make bakeoff` scored three dense models, two sparse models, and three rerank choices on `evals/datasets/v1.jsonl` (152 rows, 47 indexed files, k = 5), plus the old hash retrieval. Every model downloaded. In this pass a passage score existed only with a reranker, and the cutoff maximized balanced accuracy over all rows. Latency is time inside `search` on one 8-core laptop CPU while other jobs ran, so it is relative. Full grid, as printed (53 minutes):

```text
config                                                                    recall    mrr    ctx  facts  abstP  abstR    inj     cut  index_s   p50_ms   p95_ms
hash-baseline                                                              0.637  0.478  0.179  0.632  0.000  0.000  0.901       -      0.0      1.5      1.9
BAAI/bge-small-en-v1.5 + Qdrant/bm25 + no rerank                           0.811  0.659  0.256  0.821  0.000  0.000  0.882       -      5.0     14.8     23.0
BAAI/bge-small-en-v1.5 + Qdrant/bm25 + Xenova/ms-marco-MiniLM-L-12-v2      0.585  0.491  0.168  0.581  0.429  0.943  0.921   3.834      5.0    893.1   1899.8
BAAI/bge-small-en-v1.5 + Qdrant/bm25 + BAAI/bge-reranker-base              0.731  0.611  0.229  0.722  0.586  0.971  0.901  -0.894      5.0   2566.8   7706.1
BAAI/bge-small-en-v1.5 + Qdrant/minicoil-v1 + no rerank                    0.811  0.658  0.260  0.821  0.000  0.000  0.882       -      9.2     25.7     46.4
BAAI/bge-small-en-v1.5 + Qdrant/minicoil-v1 + Xenova/ms-marco-MiniLM-L-12-v2   0.585  0.491  0.168  0.581  0.429  0.943  0.921   3.834      9.2    558.0    988.5
BAAI/bge-small-en-v1.5 + Qdrant/minicoil-v1 + BAAI/bge-reranker-base       0.731  0.611  0.229  0.722  0.586  0.971  0.901  -0.894      9.2   1833.7   3237.2
google/embeddinggemma-300m + Qdrant/bm25 + no rerank                       0.869  0.708  0.280  0.863  0.000  0.000  0.928       -     18.1     26.3     37.6
google/embeddinggemma-300m + Qdrant/bm25 + Xenova/ms-marco-MiniLM-L-12-v2   0.585  0.491  0.169  0.581  0.429  0.943  0.921   3.834     18.1    555.5   1118.9
google/embeddinggemma-300m + Qdrant/bm25 + BAAI/bge-reranker-base          0.722  0.609  0.227  0.714  0.586  0.971  0.901  -0.894     18.1   1976.7   3568.7
google/embeddinggemma-300m + Qdrant/minicoil-v1 + no rerank                0.856  0.706  0.277  0.850  0.000  0.000  0.928       -     21.1     40.0     54.9
google/embeddinggemma-300m + Qdrant/minicoil-v1 + Xenova/ms-marco-MiniLM-L-12-v2   0.585  0.491  0.169  0.581  0.429  0.943  0.921   3.834     21.1    586.0   1163.3
google/embeddinggemma-300m + Qdrant/minicoil-v1 + BAAI/bge-reranker-base   0.722  0.609  0.227  0.714  0.586  0.971  0.901  -0.894     21.1   1988.9   3889.4
Qwen/Qwen3-Embedding-0.6B-Q + Qdrant/bm25 + no rerank                      0.801  0.647  0.255  0.821  0.000  0.000  0.868       -     86.4    301.6    515.5
Qwen/Qwen3-Embedding-0.6B-Q + Qdrant/bm25 + Xenova/ms-marco-MiniLM-L-12-v2   0.585  0.491  0.169  0.581  0.429  0.943  0.921   3.834     86.4    862.8   1509.0
Qwen/Qwen3-Embedding-0.6B-Q + Qdrant/bm25 + BAAI/bge-reranker-base         0.731  0.611  0.227  0.722  0.586  0.971  0.901  -0.894     86.4   2149.6   3802.9
Qwen/Qwen3-Embedding-0.6B-Q + Qdrant/minicoil-v1 + no rerank               0.801  0.653  0.255  0.821  0.000  0.000  0.868       -     79.2    273.9    328.0
Qwen/Qwen3-Embedding-0.6B-Q + Qdrant/minicoil-v1 + Xenova/ms-marco-MiniLM-L-12-v2   0.585  0.491  0.168  0.581  0.429  0.943  0.921   3.834     79.2    717.2   1091.9
Qwen/Qwen3-Embedding-0.6B-Q + Qdrant/minicoil-v1 + BAAI/bge-reranker-base   0.731  0.611  0.227  0.722  0.586  0.971  0.901  -0.894     79.2   1852.3   3236.4
```

The same dense and sparse pairs with the ranking before the cutoff (`raw_rec`, `raw_mrr`):

```text
config                                                                   raw_rec raw_mrr  recall    mrr    ctx  facts  abstP  abstR    inj     cut  index_s   p50_ms   p95_ms
hash-baseline                                                              0.637   0.478   0.637  0.478  0.179  0.632  0.000  0.000  0.901       -      0.0      1.6      2.0
BAAI/bge-small-en-v1.5 + Qdrant/bm25 + no rerank                           0.811   0.659   0.811  0.659  0.256  0.821  0.000  0.000  0.882       -      3.3      8.8     13.1
BAAI/bge-small-en-v1.5 + Qdrant/bm25 + Xenova/ms-marco-MiniLM-L-12-v2      0.795   0.652   0.585  0.491  0.168  0.581  0.429  0.943  0.921   3.834      3.3    475.4   2372.2
BAAI/bge-small-en-v1.5 + Qdrant/bm25 + BAAI/bge-reranker-base              0.829   0.677   0.731  0.611  0.229  0.722  0.586  0.971  0.901  -0.894      3.3   1873.0   5708.2
google/embeddinggemma-300m + Qdrant/bm25 + no rerank                       0.869   0.708   0.869  0.708  0.280  0.863  0.000  0.000  0.928       -     92.4     76.8    242.8
google/embeddinggemma-300m + Qdrant/bm25 + Xenova/ms-marco-MiniLM-L-12-v2   0.808   0.655   0.585  0.491  0.169  0.581  0.429  0.943  0.921   3.834     92.4    646.9   1382.1
google/embeddinggemma-300m + Qdrant/bm25 + BAAI/bge-reranker-base          0.838   0.685   0.722  0.609  0.227  0.714  0.586  0.971  0.901  -0.894     92.4   2506.8   6740.8
```

What this pass showed:

- `bge-reranker-base` cost 1.8 to 2.6 s p50 per search, and `ms-marco-MiniLM-L-12-v2` 0.5 to 0.9 s. Either one alone uses most of a voice turn.
- With the balanced-accuracy cutoff, the reranked default refused 19 of 20 paraphrase questions in `make eval` (recall@5 0.050).
- Reranking barely helped the ranking: `bge-reranker-base` moved `bge-small` from 0.811 to 0.829 and pulled `embeddinggemma-300m` down from 0.869 to 0.838.
- Without a reranker, `embeddinggemma-300m` + `bm25` ranked best (recall@5 0.869) at 26 ms p50.

### Second pass: dense cosine, asymmetric cutoff

The chosen config plus the strongest small alternative, with the cutoff calibrated on the first half and abstention scored on the held-out half (`--dense google/embeddinggemma-300m BAAI/bge-small-en-v1.5 --sparse Qdrant/bm25 --rerank none`, 76 seconds). The hash baseline row now runs through `kb_rag` with titles in the chunk text, so it differs slightly from the first pass.

```text
config                                                           raw_rec raw_para  recall   para    mrr  facts  abstP  abstR    inj     cut  index_s   p50_ms   p95_ms
hash-baseline                                                      0.658    0.075   0.658  0.075  0.519  0.671  0.000  0.000  0.882       -      0.2      4.6      6.2
google/embeddinggemma-300m + Qdrant/bm25 + no rerank               0.869    0.583   0.869  0.583  0.708  0.863  0.800  0.286  0.928   0.379     15.2     31.6    287.7
BAAI/bge-small-en-v1.5 + Qdrant/bm25 + no rerank                   0.811    0.317   0.811  0.317  0.659  0.821  1.000  0.500  0.901   0.634     42.9     23.5     53.6
```

## Why these defaults

Quality first, then latency, inside a one-second turn.

- `embeddinggemma-300m` + `bm25` has the best recall@5 (0.869) and MRR (0.708) of any config in either pass, and the best injection safety (0.928).
- Its cutoff costs nothing on grounded questions: recall@5 and paraphrase recall are the same before and after (0.869 and 0.583). It catches only clear misses: held-out abstention precision 0.800, recall 0.286.
- `bge-small` catches more misses at its cutoff (recall 0.500) but ranks worse, most of all on paraphrases (0.317 against 0.583).
- Search p50 is tens of milliseconds, against seconds with a cross-encoder.

## Final numbers

`make eval` with the defaults (61 seconds wall, about 1 minute; latency moves with machine load):

```text
category                      owner        n  recall@5    mrr  ctx_prec  facts  abstain  inj_safe
answerable                                37     1.000  0.881     0.254  1.000    0.000     1.000
paraphrase                                20     0.583  0.395     0.140  0.600    0.050     1.000
multi_hop                                 15     0.967  0.900     0.680  0.867    0.000     1.000
follow_up                                 15     0.867  0.767     0.267  0.867    0.000     1.000
off_topic                     retrieval   12         -      -         -      -    0.833     1.000
unanswerable_out_of_scope     retrieval   15         -      -         -      -    0.000     1.000
unanswerable_false_premise    answer      10     0.850  0.603     0.240  0.900    0.000     0.800
unanswerable_underspecified   answer       8         -      -         -      -    0.125     1.000
unanswerable_partial          answer      10     0.900  0.770     0.200  0.900    0.000     1.000
injection                                 10     0.800  0.367     0.200  0.800    0.000     0.100
overall                                  152     0.869  0.708     0.280  0.863    0.079     0.928

latency p50 102.1 ms  p95 266.1 ms
owner: retrieval should abstain; answer is judged live on the model's reply. Abstention precision and recall use the held-out half only.
gate                           score  threshold
recall_at_k                    0.869      0.840
mrr                            0.708      0.680
context_precision              0.280      0.260
fact_recall                    0.863      0.840
abstention_precision           0.800      0.750
abstention_recall              0.286      0.250
injection_safety               0.928      0.900
```

## What the numbers say

- The hash baseline is clearly worse: recall@5 0.658 against 0.869, paraphrase recall 0.075 against 0.583, and no abstention.
- Retrieval catches most off-topic chat (abstains on 10 of 12) and almost no in-domain out-of-scope question (0 of 15). Those look like real questions to an embedding model. They are left to the answer model, which sees passages that do not answer them.
- Paraphrases are the weak spot of the ranking itself (0.583), not of abstention.
- Poisoned pages rank first for 9 of 10 injection rows and for 2 of 10 false-premise rows. Every other category stays at 1.000 `inj_safe`. Retrieval cannot tell a forum post from policy; the answer layer must treat passages as untrusted data.
- `embeddinggemma-300m` is published under Google's Gemma terms, not an OSI license. That is acceptable for this demo; a product shipping it should check the terms.

## Consequences

- The first ingest or search downloads about 1.2 GB of models. The CI eval job caches them; unit tests use the hashed embedder.
- Changing a model or the threshold means `make bakeoff`, `make eval`, and new `evals/thresholds.json` floors from the printout.
- A collection created with one dense model cannot take vectors of another size. Changing `dense` needs a new collection and a re-index.
