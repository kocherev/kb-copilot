# Judge labels

Human labels used to check the LLM judges. None are committed yet.

## Format

One JSON object per line:

```json
{"id": "refund-timing", "judge": "faithful", "label": true, "note": "Every claim is in billing/refunds.md."}
```

| Field | Meaning |
| --- | --- |
| `id` | A row id from `evals/datasets/v1.jsonl`. |
| `judge` | `faithful`, `correct`, `refusal`, or `citation`. |
| `label` | `true` when a person judges that the answer passes this check. |
| `note` | Optional. Why. Not read by the code. |

Label the same answers file that was judged. One answer can carry up to four rows, one per judge.

## Check a judge

```bash
make eval-live ANSWERS=path/to/answers.jsonl
make judge-calibrate RUN=evals/runs/<date>-<sha>.jsonl LABELS=evals/labels/<name>.jsonl
```

The second command prints, per judge, how many rows have a label, the true positive rate (judge passes when the person passed it), and the true negative rate (judge fails when the person failed it). It makes no API call.

Label at least 20 passes and 20 fails per judge before trusting a rate. Change the judge prompt and bump `PROMPT_VERSION` in `evals/src/kb_evals/judge.py` when a rate is low, then judge and compare again.
