---
name: prove-it-works
description: >
  Run unit tests and the offline eval before a pull request, and paste the
  score table. Use when finishing a change to this repo.
---

# Prove it works

A change is done when a command you can rerun shows the behavior. Read `skills/tests/SKILL.md` before writing the test.

- Call the route, render the screen, or parse the file. "It typechecks" is a separate check.
- Keep the check in the repo when it can run without a private account.
- Prefer a test over a one-time manual step when the behavior is local.
- If a check did not run, name the command and why it did not run.

## Always

```bash
./scripts/check.sh
```

That command installs from the lockfiles, lints, typechecks, runs the unit tests, runs `make eval`, and checks `docker compose config`. It runs gitleaks when the binary is on `PATH`.

`docker compose config` does not prove the containers boot. If you did not run `docker compose up`, say so in the pull request.

## Evals

`make eval` prints a table with one row per category (`recall@5`, `mrr`, `ctx_prec`, `facts`, `abstain`, `inj_safe`), then the gate: each metric with its score and its floor from `evals/thresholds.json`. Exit status 1 means a score is under its floor.

Paste that printout in the pull request when the diff touches retrieval, chunking, embeddings, citations, the system prompt, or the dataset. The table in `README.md` has to match a fresh printout. Copy the numbers. Do not round them into a story.

Web-only copy and styles still go through `./scripts/check.sh`. You do not need a second paste of an unchanged table.

## What to assert

For the session UI, the rendered transcript text and the citation chips under a line are the check. For ingest, the document `status` from `GET /products/{id}/documents` and the Qdrant payload are the check. A green import is not done.
