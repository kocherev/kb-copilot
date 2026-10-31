---
name: working-style
description: >
  How to change this repo. Smallest complete diff, a named data shape,
  tests of observable behavior, and a separate reasoning budget per role
  when work is split. Use on any code change, together with ponytail.
---

# Working style

Use this with `skills/ponytail`. Ponytail picks the smallest complete change. This file says how to shape that change and how to check it. The two apply together. ponytail-mode is the source of the sequencing and verification rules. pstack is the source of the per-role budget.

## Before code

Name the data. If the change is stateful, put the states in a type or a table before writing branches. An ingest job is `queued`, then `indexing`, then `indexed` or `failed`. Chunk payloads carry `product_id` and `source_url`. The RAG package stays free of the HTTP app and the database driver.

Read the callers, tests, and exports the change touches. That list is the scope.

## Checks

A test asserts something a caller can observe. `GET /health` returns `{"status":"ok"}`. A private helper's call count is not a test.

`./scripts/check.sh` is the full local check. It runs the web lint, typecheck, and tests, then the Python lint, format, typecheck, and tests, then `docker compose config`. A compile on its own is not done.

## Sequence

One verifiable slice at a time. The job row and the chunk payload land before product config UI, a live session, or an eval gate.

## Role budgets

When a change is split across people or helpers, give each role its own reasoning budget.

- Implementation of a specified change uses a standard budget.
- Judgment, prose, and API shape use a higher budget.
- Review of a diff uses a higher budget, and it is a separate pass from the one that wrote the diff.
- Mechanical edits use a lower budget.

Record the split in the pull request when you used one. Do not write a vendor model name into this repository.

## Prose

Short sentences. One thought each. Keep a comment only when the code cannot show the reason. Docs name the command to run and the directory it affects.
