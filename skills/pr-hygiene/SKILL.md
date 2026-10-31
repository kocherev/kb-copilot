---
name: pr-hygiene
description: >
  Branch, commit, and pull request habits. Small diffs, no secrets, no
  editor or agent names in history. Use before committing or opening a PR.
---

# Pull request hygiene

Branch from `main`. Keep the branch name short and specific, as in `feat/docs-skills`. Do not put an editor name or a coding-agent name in the branch, the commit, the diff, or CI.

One behavior per pull request. Land it on `main`. Do not force-push a branch someone else is using.

## Commits

The subject is an imperative sentence. A conventional prefix (`feat:`, `fix:`, `docs:`) matches the earlier history. Later commits drop the prefix when the sentence is already specific. Either form is fine.

Do not add a trailer that names an editor or an agent. Do not commit `.env`, a key, a token, or a live password. `.env.example` stays placeholders.

## Body

Three sections:

1. Summary. What changed for a reader of the repo.
2. Proof. The command and what it printed. For retrieval changes, include the `make eval` table.
3. Notes. What you did not run, and any limit that remains.

`./scripts/check.sh` is the local gate. CI repeats it, including gitleaks. If gitleaks is not on your `PATH`, say so. CI still runs it.

## Docs in the same diff

A behavior change updates the README section that describes it. The architecture diagram and the eval table are claims about this tree. A stale number is a bug.
