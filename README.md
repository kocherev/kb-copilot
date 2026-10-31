# kb-copilot

Upload a knowledge base, index it, and talk with a support agent that can see your screen. Ingest writes hybrid chunks to Qdrant and tracks the job in Postgres. Live sessions, the MCP server, and eval datasets are later changes.

## Layout

| Path | What it is |
| --- | --- |
| `apps/web` | Next.js app. The homepage uses a copied Honest UI button. |
| `services/api` | FastAPI. `GET /health` returns `{"status":"ok"}`. |
| `services/agent` | LiveKit Agents worker. It builds and stays idle. It does not join a room. |
| `services/mcp` | Empty home for a later tool server. |
| `packages/rag` | Parse, chunk, and hybrid upsert into Qdrant. |
| `evals` | `exact_match` only. No datasets. |

Working notes for changes live in `WORKING.md`. The hiring-theme checklist is `docs/jd-fit.md`.

The homepage button is Honest UI source in `apps/web/src/components/ui`. Later UI primitives come from [ds.asanshay.com](https://ds.asanshay.com/) first.

## Prerequisites

- Node.js 22 and pnpm 10.33.4
- Python 3.12 and [uv](https://docs.astral.sh/uv/) 0.13.6
- Docker with Compose v2

## Local setup

```bash
cp .env.example .env
pnpm install
uv sync --all-packages --group dev
docker compose up --build
```

- Web: http://localhost:3000
- API health: http://localhost:8000/health
- Qdrant readiness: http://localhost:6333/readyz

`/readyz` returns plain text and HTTP 200. Do not parse that body as JSON. The API container waits with `scripts/wait_for_http.py`, which checks the status code only.

Compose points the API at the `postgres` and `qdrant` hostnames. `.env` keeps `localhost` for commands you run on the host.

The agent container is part of `docker compose up`. It prints one line and waits. It does not open a LiveKit session.

## Ingest

Sample pages live in `demo/docs`. They are original text and use the MIT license in the repository root. Markdown, HTML, and PDF are accepted. `directory` must stay inside `KB_DATA_ROOT`.

```bash
curl -s -X POST http://localhost:8000/products/demo/documents \
  -H 'content-type: application/json' \
  -d '{"directory":"demo/docs"}'
```

The job `status` becomes `indexed`. `status_log` records `queued`, then `indexing`, then `indexed`. `GET /ingest-jobs/{id}` returns the same job.

Chunks land in the Qdrant collection `kb_chunks`. Each payload has `product_id` and `source_url`. The dense vector is a local hash, so this step needs no model key. The sparse vector stores term counts, and Qdrant applies an IDF modifier to that vector. A file upload uses `upload://<name>` as `source_url`. A directory upload uses the file URI.

### Optional LiveKit server

```bash
docker compose --profile livekit up
```

That profile runs `livekit-server --dev`. The dev process does not read `LIVEKIT_API_KEY` or `LIVEKIT_API_SECRET`. Those variables in `.env.example` are placeholders for a later non-dev deployment.

## Tests and CI

GitHub Actions (`.github/workflows/ci.yml`) runs, on pull requests and on pushes to `main`:

- web lint, typecheck, unit tests, and `pnpm build`
- Python lint, format check, typecheck, and unit tests
- `docker compose config`
- a gitleaks scan

Run the same checks locally:

```bash
./scripts/check.sh
```

`check.sh` runs the lint, typecheck, test, and compose steps. It runs gitleaks when the binary is on your `PATH`. CI installs gitleaks itself.

One package at a time:

```bash
pnpm --filter web test
uv run pytest services/api/tests
uv run pytest packages/rag/tests
uv run pytest services/agent/tests
uv run pytest evals/tests
```

## Secrets

`.env.example` is placeholders. Do not commit `.env`, API keys, or live database passwords. CI fails the gitleaks job when a secret is committed.
