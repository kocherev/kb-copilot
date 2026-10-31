# Agent guide

Read this before changing the repository. It is enough to install, test, and score the demo knowledge base. The order of a code change is in `WORKING.md`.

## Map

| Path | What it is |
| --- | --- |
| `apps/web` | Next.js App Router app. Product config, upload, and the LiveKit session. |
| `services/api` | FastAPI. Products, ingest jobs, and `POST /sessions`. |
| `services/agent` | LiveKit worker `kb-support`. Voice, screen share, and `search_kb`. |
| `services/mcp` | stdio MCP server for `search_kb` and `get_product`. |
| `packages/rag` | Parse, chunk, embed, and hybrid query. No HTTP and no Postgres. |
| `evals` | `make eval`. Dataset, scorers, and `evals/thresholds.json`. |
| `demo/docs` | Original sample pages. MIT, same as `LICENSE`. |
| `skills` | Task notes for this repo. `.agents/skills` is the same directory. |

Postgres stores products and ingest jobs. Qdrant stores chunks in `kb_chunks` with `product_id` and `source_url`. The worker logs latency as JSON on stdout. It does not write a turn table.

## Commands

From a clean checkout, one command installs, lints, typechecks, runs unit tests, runs the offline eval, and checks the Compose file:

```bash
./scripts/check.sh
```

That script expects Node.js 22, pnpm 10.33.4, Python 3.12, uv 0.13.6, and Docker Compose v2 on `PATH`. It runs gitleaks when the binary is installed. CI installs gitleaks 8.30.1 itself.

Print the eval table on its own:

```bash
uv sync --all-packages --group dev
make eval
```

`make eval` is `uv run python -m kb_evals`. It indexes `demo/docs` in memory. It does not need Docker, LiveKit, or a model key.

Start the local stack:

```bash
cp .env.example .env
docker compose up --build
```

Self-hosted media server:

```bash
docker compose --profile livekit up --build
```

The dev LiveKit process uses API key `devkey` and API secret `secret`. Spoken replies on that URL need `OPENAI_API_KEY`. A `*.livekit.cloud` URL uses LiveKit Inference and does not use that key. The agent container exits when `LIVEKIT_URL` or the key pair is missing. The web app and the API still come up.

One package at a time:

```bash
pnpm --filter web test
uv run pytest services/api/tests
uv run pytest packages/rag/tests
uv run pytest services/agent/tests
uv run pytest services/mcp/tests
uv run pytest evals/tests
```

`GET /health` returns `{"status":"ok"}`. Qdrant `GET /readyz` is plain text and HTTP 200. `scripts/wait_for_http.py` checks the status code and does not parse JSON.

## Boundaries

- `packages/rag` stays free of the HTTP app and the database driver. Callers pass a Qdrant client and already-parsed sources.
- The agent name `kb-support` is set in `services/agent` and in `services/api`. Change both.
- A cited transcript line ends with `Source: <url>`. The web app, the worker, and the eval scorer share that shape. Change them together.
- An empty retrieval says exactly `That is not in the docs.`
- Dense vectors are a local token hash. A model embedding is a separate change. Re-score with `make eval` before editing the README table.
- Do not put a secret, a live password, or a filled-in `.env` in a commit. `.env.example` stays placeholders.
- The homepage button in `apps/web/src/components/ui/button.tsx` is Honest UI. Leave it. New primitives come from https://ds.asanshay.com/ first. Details are in `skills/interface/SKILL.md`.
- Consented computer actions are out of scope.
- Docs, commits, and CI do not name the editor or the coding agent that produced a change.

## Evals before a pull request

Run `./scripts/check.sh`. When the diff touches retrieval, chunking, embeddings, citations, the system prompt, or `evals/datasets`, also paste the `make eval` table into the pull request. The README table has to match that printout. Do not type the scores by hand.

The pull request body is three sections: Summary, Proof, Notes. Proof names the command and what it printed.

## Skills

Skills live in `skills/`. `.agents/skills` points at that same directory. Read the skill before the matching change.

| Path | When |
| --- | --- |
| `skills/working-style/SKILL.md` | Any code change. Named state, observable tests, role budgets. |
| `skills/ponytail/SKILL.md` | Sizing a diff. |
| `skills/prove-it/SKILL.md` | What counts as done. |
| `skills/prove-it-works/SKILL.md` | Unit tests, `make eval`, and the score table in the pull request. |
| `skills/tests/SKILL.md` | Writing or changing a test. |
| `skills/livekit-agent/SKILL.md` | The worker, dispatch, screen share, voice, or citations. |
| `skills/rag-index-query/SKILL.md` | Readers, chunking, embeddings, or the Qdrant query. |
| `skills/typescript-best-practices/SKILL.md` | `apps/web`. |
| `skills/interface/SKILL.md` | Any UI change. |
| `skills/make-interfaces-feel-better/SKILL.md` | Type, surfaces, motion, icons. |
| `skills/design-engineering/SKILL.md` | Motion and component feel. |
| `skills/design-catalog/SKILL.md` | Pointer to the design-engineering index. |
| `skills/technical-writing/SKILL.md` | README and other public docs. |
| `skills/unslop/SKILL.md` | Docs, commits, and review text. |
| `skills/pr-hygiene/SKILL.md` | Branch, commit, pull request, secrets. |
