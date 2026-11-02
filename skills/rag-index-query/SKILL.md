---
name: rag-index-query
description: >
  Change parsing, chunking, the embedding models, or the Qdrant query, then
  re-check the eval baseline. Use when editing packages/rag or search_kb.
---

# Index and query

`packages/rag` parses documents, chunks them, indexes them, and runs hybrid search. It does not import the API or Postgres. Callers pass an `AsyncQdrantClient`, `Source` values, and optionally `RetrievalSettings`.

## Documents

`SUPPORTED_SUFFIXES` are `.md`, `.markdown`, `.txt`, `.html`, `.htm`, and `.pdf`. A file over `MAX_BYTES` (2_000_000) is rejected. Hidden path segments are skipped.

`read_source(path, root)` stores the path relative to `root`. An upload stores `upload://<name>`. `index_sources` rejects an absolute path or a `file:` URI. HTML h1 to h3 become markdown headings.

The API refuses a `directory` that resolves outside `KB_DATA_ROOT`. That check stays in `services/api`.

## Chunks

`chunk_text` splits at headings and groups sentences up to 120 words. Each chunk carries `title` (nearest heading) and `anchor` (its slug). Text before any heading, and PDF text, use the page title from the file name and no anchor.

## Index

One collection, `kb_chunks`, created once by `ensure_collection`: a dense vector, a sparse vector with the IDF modifier, a tenant keyword index on `product_id`, and a keyword index on `source`. Point ids are stable per product, source, and chunk. Re-indexing a source upserts, then deletes the chunks it no longer has. `delete_source` removes one source.

## Query

`search` embeds the query, prefetches dense and sparse candidates for the product, fuses them with RRF, and scores each passage by dense cosine. It abstains, with no passages, when the best score is under `abstain_threshold`. A reranker is an opt-in setting and is off by default because it cost about 2 s per search.

Defaults are in `RetrievalSettings`: `google/embeddinggemma-300m`, `Qdrant/bm25`, no reranker, threshold 0.379. Why is in `docs/decisions/0001-retrieval.md`.

Tests pass `kb_rag.testing.HASH_SETTINGS` so they never download a model.

## After a retrieval change

```bash
make eval
make bakeoff   # when a model or the threshold changes
```

Update `evals/thresholds.json` and the README table from the printout. Do not invent a score.
