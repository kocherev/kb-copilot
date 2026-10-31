# kb-copilot

Upload a knowledge base, index it, and talk with a support agent. Ingest writes hybrid chunks to Qdrant and tracks the job in Postgres. Product config is a name, a one-paragraph description, a tone, and refusal rules, stored in Postgres. A session joins a LiveKit room with the microphone and a screen share, and the agent answers by voice. Offline evals for the demo docs run with `make eval`.

## Layout

| Path | What it is |
| --- | --- |
| `apps/web` | Next.js app. Create a product, edit its config, upload documents, and start a session. The homepage button is Honest UI. |
| `services/api` | FastAPI. `GET /health` returns `{"status":"ok"}`. Product config is stored in Postgres. `POST /sessions` mints a LiveKit token and dispatches the agent. |
| `services/agent` | LiveKit Agents worker. It joins a room when dispatched, with `product_id` in the job metadata. |
| `services/mcp` | MCP server for `search_kb` and `get_product`. Run notes are in `services/mcp/README.md`. |
| `packages/rag` | Parse, chunk, and hybrid upsert into Qdrant. |
| `evals` | Offline dataset, scorers, and the `make eval` threshold gate. See `evals/README.md`. |

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

The agent container is part of `docker compose up`. It registers with LiveKit and waits for a dispatch. It exits if `LIVEKIT_URL` or the API key pair is missing.

## Ingest

Sample pages live in `demo/docs`. They are original text and use the MIT license in the repository root. Markdown, HTML, and PDF are accepted. `directory` must stay inside `KB_DATA_ROOT`.

```bash
curl -s -X POST http://localhost:8000/products/demo/documents \
  -H 'content-type: application/json' \
  -d '{"directory":"demo/docs"}'
```

The job `status` becomes `indexed`. `status_log` records `queued`, then `indexing`, then `indexed`. `GET /ingest-jobs/{id}` returns the same job.

Chunks land in the Qdrant collection `kb_chunks`. Each payload has `product_id` and `source_url`. The dense vector is a local hash, so this step needs no model key. The sparse vector stores term counts, and Qdrant applies an IDF modifier to that vector. A file upload uses `upload://<name>` as `source_url`. A directory upload uses the file URI.

## Product config

`POST /products` stores the config. `GET /products/{id}` reads it. `PUT /products/{id}` replaces it. A blank field is rejected. The description must be one paragraph.

```bash
curl -s -X POST http://localhost:8000/products \
  -H 'content-type: application/json' \
  -d '{"name":"Acme","description":"Acme helps customers reset passwords.","tone":"calm and brief","refusal_rules":"Do not invent a refund policy."}'
```

Use the returned `id` to upload documents:

```bash
curl -s -X POST http://localhost:8000/products/<id>/documents \
  -F files=@notes.md
```

The web app at `/` creates a product. `/products/{id}` edits the four fields and uploads files for that id. A saved config shows the word Saved.

`render_system_prompt` in `services/agent` includes the name, description, tone, and refusal rules. A directory upload such as `POST /products/demo/documents` still works without a product row.

## Live session

`POST /sessions` with `{"product_id":"<uuid>"}` returns `url`, `token`, and `room`. The token lets the browser join that room and publish. The API also dispatches the agent named `kb-support` with job metadata `{"product_id":"<uuid>"}`. A missing product returns 404 and does not dispatch. Missing LiveKit settings return 503.

The worker loads that product from `GET /products/{id}` and uses it as the system prompt. It publishes a voice reply through STT, an LLM, and TTS. It subscribes to screen-share video when the browser publishes one. Each STT, LLM, and TTS metric is one JSON line on stdout, and each user or assistant turn is another JSON line with the per-turn delays. A knowledge lookup is another JSON line with `kind` set to `retrieval` and `duration_ms`.

On a `*.livekit.cloud` URL the worker uses LiveKit Inference. On any other URL, including the Compose hostname `livekit`, it uses the OpenAI plugin and `OPENAI_API_KEY`. Each product question calls `search_kb` against the Qdrant collection `kb_chunks`, filtered by `product_id`. The agent container reads `QDRANT_URL` (`http://qdrant:6333` in Compose). A matching passage is cited in the transcript. No matching passage produces `That is not in the docs.`

The web app links to `/products/{id}/session`. Start session asks for the microphone and the screen, then plays the agent with `RoomAudioRenderer`. The transcript lists speech as it arrives. A cited answer shows the source under that line.

### LiveKit Cloud

Set `LIVEKIT_URL` and `LIVEKIT_AGENT_URL` to the same `wss://<project>.livekit.cloud` URL, and set the project key pair. Leave the `livekit` profile off.

```bash
docker compose up --build
```

### Self-hosted server

```bash
docker compose --profile livekit up --build
```

That profile runs `livekit-server --dev`. The dev process does not read `LIVEKIT_API_KEY` or `LIVEKIT_API_SECRET`. Its key pair is `devkey` / `secret`. Put those in `.env`, with `LIVEKIT_URL=ws://localhost:7880` and `LIVEKIT_AGENT_URL=ws://livekit:7880`. Set `OPENAI_API_KEY` as well. The browser uses `LIVEKIT_URL`. The agent container uses `LIVEKIT_AGENT_URL` because `localhost` inside that container is not the LiveKit server.

Create a product in the web app, open Start session, allow the microphone and the screen, and speak. The agent container logs one JSON object per STT, LLM, and TTS segment.

## Tests and CI

GitHub Actions (`.github/workflows/ci.yml`) runs, on pull requests and on pushes to `main`:

- web lint, typecheck, unit tests, and `pnpm build`
- Python lint, format check, typecheck, and unit tests
- offline evals via `make eval`, failing when a score is below `evals/thresholds.json`
- `docker compose config`
- a gitleaks scan

Run the same checks locally:

```bash
./scripts/check.sh
```

`check.sh` runs the lint, typecheck, test, eval, and compose steps. It runs gitleaks when the binary is on your `PATH`. CI installs gitleaks itself.

One package at a time:

```bash
pnpm --filter web test
uv run pytest services/api/tests
uv run pytest packages/rag/tests
uv run pytest services/agent/tests
uv run pytest services/mcp/tests
uv run pytest evals/tests
```

## Secrets

`.env.example` is placeholders. Do not commit `.env`, API keys, or live database passwords. CI fails the gitleaks job when a secret is committed.
