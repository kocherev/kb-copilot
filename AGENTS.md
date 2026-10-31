# Working notes

Read this before changing the repository.

## Order

1. Name the behavior a caller can observe.
2. Add the smallest test that fails when that behavior breaks.
3. Make the smallest change that passes the test.
4. Run the test. Done means the command passed.

`./scripts/check.sh` is the full local check. A green import, by itself, is not done.

## Scope

Read the code the change touches. List callers, tests, fixtures, and config. Extra features stay out.

Take the first option that fully works:

1. Skip it when nobody asked.
2. Use a helper already in this repo.
3. Use the standard library or the platform.
4. Use a dependency that is already installed. Do not add one for a few lines.
5. One line, when a reader gets it at a glance.
6. Otherwise the minimum that works.

Do not cut validation on trust boundaries, error handling that prevents data loss, security, or accessibility.

New logic with a branch, a loop, a parser, or a security check leaves one small test.

Details are in `.agents/skills/ponytail/SKILL.md`. That note follows the MIT Ponytail rules at https://github.com/DietrichGebert/ponytail.

## Proof

Assert what a caller can observe. Hit the route, render the page, or parse the config.

Qdrant `GET /readyz` is plain text with HTTP 200. `scripts/wait_for_http.py` checks the status code and does not parse JSON. Keep it that way.

## Interface

The homepage button is Honest UI, in `apps/web/src/components/ui`, with tokens in `src/styles/honest-ui-theme.css`. Leave that button in place.

New primitives come from https://ds.asanshay.com/ before another kit.

Before changing UI, read `.agents/skills/interface/SKILL.md`.

## Words

Docs, pull requests, and commit messages follow `.agents/skills/unslop/SKILL.md`. Short sentences. Sentence-case headings. No filler.

## Skills

| Path | When |
| --- | --- |
| `.agents/skills/ponytail/SKILL.md` | Sizing a diff |
| `.agents/skills/prove-it/SKILL.md` | Before calling a change done |
| `.agents/skills/tests/SKILL.md` | Writing or changing a test |
| `.agents/skills/interface/SKILL.md` | Any UI change |
| `.agents/skills/unslop/SKILL.md` | Docs, commits, and review text |
