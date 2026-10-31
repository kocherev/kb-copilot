---
name: prove-it-works
description: >
  Run unit tests and the offline eval before a pull request, and paste the
  score table. Use when finishing a change to this repo.
---

# Prove it works

Read `skills/prove-it/SKILL.md` and `skills/tests/SKILL.md`. A change is done when a command you can rerun shows the behavior.

## Always

```bash
./scripts/check.sh
```

That command installs from the lockfiles, lints, typechecks, runs the unit tests, runs `make eval`, and checks `docker compose config`. It runs gitleaks when the binary is on `PATH`.

`docker compose config` does not prove the containers boot. If you did not run `docker compose up`, say so in the pull request.

## Evals

`make eval` prints `cases`, then `hit@k`, `mrr`, `citation_rate`, and `faithfulness`, each with a threshold. Exit status 1 means a score is under `evals/thresholds.json`.

Paste that printout in the pull request when the diff touches retrieval, chunking, embeddings, citations, the system prompt, or the dataset. The table in `README.md` has to match a fresh printout. Copy the numbers. Do not round them into a story.

Web-only copy and styles still go through `./scripts/check.sh`. You do not need a second paste of an unchanged table.

## What to assert

Hit the route, render the screen, or parse the file. For the session UI, rendered transcript text and the `Source:` label are the check. For ingest, the job status and the Qdrant payload are the check. A green import is not done.
