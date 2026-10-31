# Evals

Offline checks for the demo knowledge base. `make eval` indexes `demo/docs`, answers each row in `evals/datasets/demo.jsonl`, and prints hit@k, MRR, citation rate, and faithfulness. The command exits with status 1 when a score is below `evals/thresholds.json`.

## Run

From the repository root, after `uv sync --all-packages --group dev`:

```bash
make eval
```

The eval job in `.github/workflows/ci.yml` runs the same command. It does not call a paid model. Dense vectors are the local hash in `packages/rag`. When retrieval returns a passage, the spoken text is the `answer` field for that row. When retrieval returns nothing, the spoken text is `That is not in the docs.`

## Dataset

`evals/datasets/demo.jsonl` holds one JSON object per line. Each object has `id`, `question`, `answer`, `facts`, and `sources`. A `sources` entry is a path under `demo/docs`. An empty `sources` list is an out-of-KB question. Its answer is `That is not in the docs.`, and the run must not cite a file.

The pages in `demo/docs` are original sample text written for this repository. They use the MIT license in `LICENSE`. Each in-KB question keeps a content word from its source page, because the offline dense vector is a token hash.

## Metrics

Retrieval calls `search_kb` in the agent. That helper calls the hybrid query in `packages/rag`. `k` comes from `evals/thresholds.json` and is passed to `search_kb`. The checked-in value is 5, the default limit of that search.

hit@k follows the LlamaIndex hit rate. The score is 1 when any expected source is in the top k retrieved sources. Otherwise it is 0. MRR is the mean of the per-question reciprocal ranks. A rank starts at 1, so the first matching source scores 1 and the second scores 0.5. No match scores 0. For an out-of-KB row, both scores are 1 when retrieval returns no passage, and 0 when it returns any passage. LlamaIndex's own hit rate and MRR require a non-empty expected id list, so the empty-list case is this harness's abstention rule.

Citation rate is 1 when an in-KB answer includes a `Source:` line for an expected path. The line is the same suffix the agent appends in a transcript. For an out-of-KB row the score is 1 only when the answer has no `Source:` line.

Faithfulness does not call a model. Citation lines are ignored. The sentence `That is not in the docs.` is faithful only when no passage was retrieved. Every other sentence is faithful when its text, without the final period, appears in the retrieved passages. Whitespace is collapsed before the comparison. A number copied from a different sentence in the same passage does not pass. The case score is the fraction of sentences that pass. The printed score is the mean over the dataset.

## Thresholds

`evals/thresholds.json` stores `k` and the minimum mean for `hit_at_k`, `mrr`, `citation_rate`, and `faithfulness`. CI fails when `make eval` reports a lower score.
