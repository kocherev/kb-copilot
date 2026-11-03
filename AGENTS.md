# Agent guide

Read this before changing the repository. It is enough to install, test, and score the demo knowledge base. The order of a code change is in `WORKING.md`.

## Map

| Path | What it is |
| --- | --- |
| `apps/web` | Next.js App Router app. Better Auth sign-in, product config, upload, and the LiveKit session. |
| `apps/desktop` | macOS helper that joins a session room, sends screenshots, draws the agent cursor, and performs the mouse and keyboard actions the user approves, over LiveKit RPC. |
| `services/api` | FastAPI. Products, documents, the ingest queue, API keys, and `POST /sessions`. Verifies Better Auth JWTs. |
| `services/agent` | LiveKit worker `kb-support`. Gemini Live voice and vision, `search_kb`, `point_at`, `handoff_to_human`, `operate_computer`. Loads no embedding model: it calls the API. |
| `services/mcp` | stdio MCP server for `search_kb` and `get_product`. |
| `packages/rag` | Parse, chunk, embed, and hybrid query. No HTTP and no Postgres. |
| `evals` | `make eval`. Dataset, scorers, `evals/thresholds.json`, and the live answer and judge harness. |
| `demo/docs` | Original sample pages. MIT, same as `LICENSE`. |
| `docs/decisions` | Architecture decisions. `docs/decisions/README.md` is the index. |
| `skills` | Task notes for this repo. `.agents/skills` is the same directory. |

Postgres stores products, documents (with the uploaded bytes until they are indexed), ingest jobs, API keys, live sessions, their turns, the audit log, and the session rate limit. Better Auth keeps its own tables in the same database. Qdrant stores chunks in `kb_chunks` with `product_id`, `source`, `title`, `anchor`, and `text`. `source` is `upload://<name>` for an API upload, or a path relative to the directory for `read_directory`, which the evals and the selfcheck use. The worker logs latency as JSON on stdout and posts each turn to `POST /internal/turns`, which the replay page reads.

Auth: every product, document, session, and API-key route needs `Authorization: Bearer`, either a Better Auth JWT from `GET /api/auth/token` on the web app or an org API key that starts with `kb_`. `GET /products/{id}` also accepts the `X-Internal-Token` header with `INTERNAL_API_TOKEN`, which the agent sends. The agent also calls `POST /internal/search`, `POST /internal/citations`, and `POST /internal/desktop-actions` with it. The API process holds the only embedding models. `GET /health` is open. Uploads are multipart `POST /products/{id}/documents`, answered with 202. A loop in the API process indexes them.

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

`make eval` is `uv run python -m kb_evals`. It indexes `demo/docs` in memory with the default FastEmbed models, which download on first use. It does not need Docker, LiveKit, or a model key. Unit tests use the hashed embedder in `kb_rag.testing` and download nothing.

Start the local stack. The README Quickstart has the `.env` steps. The web app refuses to start until `BETTER_AUTH_SECRET` is 32 or more random characters (`openssl rand -hex 32`). Set `INTERNAL_API_TOKEN` the same way.

```bash
cp .env.example .env
docker compose up --build
```

Self-hosted media server:

```bash
docker compose --profile livekit up --build
```

The dev LiveKit process uses API key `devkey` and API secret `secret`. The agent speaks through Gemini Live on any LiveKit host and needs `GOOGLE_API_KEY`. A placeholder key pair such as `replace-me` counts as missing. `POST /sessions` then returns 503. The agent container exits at start with one line that names the missing setting. The web app and the API still come up. The `migrate` service applies the Alembic migrations before the API starts.

Commands that need a key:

```bash
make eval-answers   # GOOGLE_API_KEY. Answers every eval row with gemini-3.8-flash
make eval-live      # ANTHROPIC_API_KEY. Judges those answers, claude-haiku-5-5 unless KB_JUDGE_MODEL is set
uv run python -m kb_agent.selfcheck --image services/agent/tests/fixtures/billing-screen.png --question "What does the red banner say?"
```

`make eval-live` reads the file `make eval-answers` wrote. Git ignores `evals/runs/`. The selfcheck exits 1 when the live model was billed no image tokens.

One package at a time:

```bash
pnpm --filter web test
uv run pytest services/api/tests
uv run pytest packages/rag/tests
uv run pytest services/agent/tests
uv run pytest services/mcp/tests
uv run pytest apps/desktop/tests
uv run pytest evals/tests
```

`GET /health` returns `{"status":"ok"}`. Qdrant `GET /readyz` is plain text and HTTP 200. `scripts/wait_for_http.py` checks the status code and does not parse JSON.

## Boundaries

- `packages/rag` stays free of the HTTP app and the database driver. Callers pass a Qdrant client and already-parsed sources.
- The agent name `kb-support` and the data-channel topics are in `services/agent/src/kb_agent/protocol.py` and `apps/web/src/lib/protocol.ts`. `services/api` repeats the agent name. `services/agent/tests/test_protocol.py` fails when they drift.
- Citations travel as `citations` data messages, not as text in the transcript. Change the worker, `apps/web/src/lib/protocol.ts`, and the page together.
- An empty retrieval says exactly `That is not in the docs.`
- Retrieval models and the abstain threshold live in `RetrievalSettings` in `packages/rag`. Changing one means `make bakeoff`, `make eval`, new `evals/thresholds.json` floors, and a README table pasted from the printout.
- Do not put a secret, a live password, or a filled-in `.env` in a commit. `.env.example` stays placeholders.
- The homepage button in `apps/web/src/components/ui/button.tsx` is Honest UI. Leave it. New primitives come from https://ds.asanshay.com/ first. Details are in `skills/interface/SKILL.md`.

## Evals before a pull request

Run `./scripts/check.sh`. When the diff touches retrieval, chunking, embeddings, citations, the system prompt, or `evals/datasets`, also paste the `make eval` table into the pull request. The README table has to match that printout. Do not type the scores by hand.

The pull request body is three sections: Summary, Proof, Notes. Proof names the command and what it printed.

## Skills

Skills live in `skills/`. `.agents/skills` points at that same directory. Read the skill before the matching change.

| Path | When |
| --- | --- |
| `skills/working-style/SKILL.md` | Any code change. Named state, observable tests, role budgets. |
| `skills/ponytail/SKILL.md` | Sizing a diff. |
| `skills/prove-it-works/SKILL.md` | What counts as done. Unit tests, `make eval`, and the score table in the pull request. |
| `skills/tests/SKILL.md` | Writing or changing a test. |
| `skills/livekit-agent/SKILL.md` | The worker, dispatch, screen share, voice, or citations. |
| `skills/rag-index-query/SKILL.md` | Readers, chunking, embeddings, or the Qdrant query. |
| `skills/typescript-best-practices/SKILL.md` | `apps/web`. |
| `skills/interface/SKILL.md` | Any UI change. |
| `skills/make-interfaces-feel-better/SKILL.md` | Type, surfaces, motion, icons. |
| `skills/design-engineering/SKILL.md` | Motion and component feel. |
| `skills/technical-writing/SKILL.md` | README and other public docs. |
| `skills/unslop/SKILL.md` | Docs, commits, and review text. |
| `skills/pr-hygiene/SKILL.md` | Branch, commit, pull request, secrets. |
