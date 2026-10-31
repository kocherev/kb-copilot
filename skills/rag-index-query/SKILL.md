---
name: rag-index-query
description: >
  Change parsing, chunking, the local embedding, or the Qdrant query, then
  re-check the eval baseline. Use when editing packages/rag or search_kb.
---

# Index and query

`packages/rag` parses documents, chunks them, and runs hybrid search. It does not import the API or Postgres. Callers pass a `QdrantClient` and `Source` values.

## Documents

`SUPPORTED_SUFFIXES` are `.md`, `.markdown`, `.txt`, `.html`, `.htm`, and `.pdf`. A file over `MAX_BYTES` (2_000_000) is rejected. Hidden path segments are skipped.

Markdown files set `Source.markdown`. HTML is reduced to text first. `source_url` is chosen by the caller: a directory upload uses the file URI, a file upload uses `upload://<name>`.

The API refuses a `directory` that resolves outside `KB_DATA_ROOT`. That check stays in `services/api`, not in this package.

## Chunks

`chunk_text` splits markdown with LlamaIndex `MarkdownNodeParser`, then builds sentence windows of radius 1. Other files skip the heading split and window the whole text. Empty input produces no chunks, and `index_sources` rejects a source that produces none.

## Index

One collection, `kb_chunks`. `product_id` is a payload filter, not a collection name. Each point payload is `product_id`, `source_url`, and `text`.

The dense vector is a 384-d token hash in `embed.py`. The sparse vector is term counts. Qdrant stores it as `bm25` with an IDF modifier. Query fuses dense and sparse with reciprocal rank fusion. Prefetch is `max(limit, 8)`. The default limit is 5, which is `k` in `evals/thresholds.json`.

Re-index of one source deletes that product and `source_url`, then upserts. Other sources stay. A failure midway keeps the earlier files in that call.

Do not add a hosted embedding here. A denser model is a separate change, and it moves the eval baseline. The offline gate has to pass without a model key.

## After a retrieval change

```bash
make eval
```

Compare the printout to `evals/thresholds.json` and to the table in `README.md`. If the numbers move, update the README from the printout. Do not invent a score. An out-of-KB row scores 1 only when retrieval returns no passage and the answer has no `Source:` line.

The agent helper `search_kb` drops a hit that shares no content token with the query. A chunking change can pass the Qdrant query and still fail that filter. Run `uv run pytest packages/rag/tests services/agent/tests/test_retrieve.py evals/tests` with `make eval`.
