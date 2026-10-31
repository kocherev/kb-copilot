# kb-copilot

Screen-share and voice support over a knowledge base you upload. The agent answers from that knowledge base, cites the passage, and this repo scores those answers before a change lands.

You upload documents, set the product name, description, tone, and refusal rules, then join a LiveKit room with your microphone and your screen. The worker searches the index for that product. A hit shows up under the spoken line as `Source:`. A miss is the sentence `That is not in the docs.`

## Architecture

```mermaid
flowchart LR
  web["apps/web"]
  api["services/api"]
  agent["services/agent"]
  mcp["services/mcp"]
  rag["packages/rag"]
  evals["evals"]
  pg[(Postgres)]
  qd[(Qdrant)]
  room["LiveKit room"]

  web -->|"upload, config, token"| api
  web -->|"mic and screen"| room
  api --> pg
  api --> rag
  rag --> qd
  agent -->|"join as kb-support"| room
  agent -->|"load product"| api
  agent --> rag
  mcp --> rag
  mcp -->|"get_product"| api
  evals --> rag
  evals --> agent
```

The browser talks to the API for products, uploads, and the LiveKit token. Postgres stores the product and the ingest job. `packages/rag` parses, chunks, and upserts hybrid vectors into the Qdrant collection `kb_chunks`, filtered by `product_id`. The worker loads the product from the API, joins the room with that id in the dispatch metadata, and calls `search_kb` in-process against the same index. `services/mcp` exposes `search_kb` and `get_product` on stdio. `evals/` runs the retrieval path offline and fails the process when a score drops under `evals/thresholds.json`.

## Quickstart

These steps take about five minutes after Docker has built the images.

You need Node.js 22, pnpm 10.33.4, Python 3.12, [uv](https://docs.astral.sh/uv/) 0.13.6, and Docker Compose v2.

```bash
cp .env.example .env
pnpm install
uv sync --all-packages --group dev
docker compose up --build
```

- Web: http://localhost:3000
- API health: http://localhost:8000/health
- Qdrant readiness: http://localhost:6333/readyz

`/readyz` returns plain text and HTTP 200. Do not parse that body as JSON.

Compose points the API at the `postgres` and `qdrant` hostnames. `.env` keeps `localhost` for commands you run on the host. The API container waits with `scripts/wait_for_http.py`, which checks the status code only.

`.env.example` sets the LiveKit key pair to `replace-me`. The web app, API, Postgres, and Qdrant still start. The worker joins a room only after `LIVEKIT_URL` and a real key pair are set. It exits when either value is missing. Spoken replies need a model key as well. The two setups are below.

Create a product and index the sample pages. Those pages are original text under the MIT license in `LICENSE`.

```bash
curl -s -X POST http://localhost:8000/products \
  -H 'content-type: application/json' \
  -d '{"name":"Acme","description":"Acme helps customers reset passwords.","tone":"calm and brief","refusal_rules":"Do not invent a refund policy."}'
```

Use the returned `id`:

```bash
curl -s -X POST http://localhost:8000/products/<id>/documents \
  -H 'content-type: application/json' \
  -d '{"directory":"demo/docs"}'
```

`directory` must stay inside `KB_DATA_ROOT`. In Compose that root is `/app`, and the image includes `demo/docs`. The job `status` becomes `indexed`. Open http://localhost:3000/products/<id> and choose Start session.

To run the checks without starting the stack:

```bash
./scripts/check.sh
make eval
```

`./scripts/check.sh` already runs the offline eval. `make eval` prints the same table on its own.

### LiveKit Cloud

Set `LIVEKIT_URL` and `LIVEKIT_AGENT_URL` to the same `wss://<project>.livekit.cloud` URL, and set that project's key pair. Leave `OPENAI_API_KEY` empty. The worker uses LiveKit Inference on a `*.livekit.cloud` host. Leave the `livekit` profile off.

```bash
docker compose up --build
```

### Self-hosted server

```bash
docker compose --profile livekit up --build
```

That profile runs `livekit-server --dev`. The dev process does not read `LIVEKIT_API_KEY` or `LIVEKIT_API_SECRET`. Its key pair is `devkey` / `secret`. Put those in `.env`, with `LIVEKIT_URL=ws://localhost:7880` and `LIVEKIT_AGENT_URL=ws://livekit:7880`. Set `OPENAI_API_KEY` as well. The browser uses `LIVEKIT_URL`. The agent container uses `LIVEKIT_AGENT_URL` because `localhost` inside that container is not the LiveKit server.

## Demo

The session page asks for the microphone and the screen. After the room connects, the transcript lists each turn. A cited answer shows `Source:` under the agent's line. The label is the file name, here `billing.md`.

![Session page for Acme before the room connects. The button reads Start session.](docs/session-start.png)

![Session transcript for Acme. The agent answers the refund question and the line under it reads Source: billing.md.](docs/session-transcript.png)

What you would hear for "How long do refunds take?": the indexed sentence is "Refunds take 5 business days after the review team approves the request." The worker speaks the answer with the configured TTS. The transcript adds `Source: billing.md`. The system prompt tells the agent not to read the source URL aloud.

These pictures are the session components with that sample turn. They are not a recording of a live room. A live capture needs LiveKit credentials and a model key.

## Eval results

`make eval` indexes `demo/docs` in memory, answers the 40 rows in `evals/datasets/demo.jsonl`, and prints this table. The command exits 1 when a score is below the threshold. These numbers are that printout for the committed dataset.

| Metric | Score | Threshold |
| --- | --- | --- |
| hit@5 | 1.000 | 1.000 |
| mrr | 1.000 | 1.000 |
| citation_rate | 1.000 | 1.000 |
| faithfulness | 1.000 | 1.000 |

`k` is 5, from `evals/thresholds.json`. Hit rate, MRR, citation rate, and faithfulness are defined in `evals/README.md`. The run does not call a paid model. When retrieval returns a passage, the scored text is the dataset `answer` plus the same `Source:` suffix the transcript uses. When it returns nothing, the text is `That is not in the docs.`

## MCP

`services/mcp` speaks MCP over stdio. `search_kb` uses the same retrieval function as the agent. `get_product` reads `GET /products/{id}`.

Start the stack from the quickstart, then point the client at this repo. Stdout is the protocol. The longer notes, including the tool arguments, are in `services/mcp/README.md`.

```json
{
  "mcpServers": {
    "kb-copilot": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/kb-copilot",
        "--package",
        "kb-mcp",
        "kb-mcp"
      ],
      "env": {
        "QDRANT_URL": "http://localhost:6333",
        "API_URL": "http://localhost:8000"
      }
    }
  }
}
```

## Layout

| Path | What it is |
| --- | --- |
| `apps/web` | Next.js app. Create a product, edit its config, upload documents, and start a session. |
| `services/api` | FastAPI. Product config and ingest jobs live in Postgres. `POST /sessions` mints a LiveKit token and dispatches the agent. |
| `services/agent` | LiveKit Agents worker. It joins a room when dispatched, with `product_id` in the job metadata. |
| `services/mcp` | MCP server for `search_kb` and `get_product`. |
| `packages/rag` | Parse, chunk, and hybrid upsert into Qdrant. |
| `evals` | Golden questions, scorers, and the threshold gate. |

The command map for changes is `AGENTS.md`. The hiring-theme checklist is `docs/jd-fit.md`.

## Ingest

Markdown, HTML, and PDF are accepted. A file upload uses `upload://<name>` as `source_url`. A directory upload uses the file URI.

```bash
curl -s -X POST http://localhost:8000/products/demo/documents \
  -H 'content-type: application/json' \
  -d '{"directory":"demo/docs"}'
```

`POST /products/demo/documents` still works without a product row. A session does not: a missing product returns 404 and does not dispatch.

The job `status` becomes `indexed`. `status_log` records `queued`, then `indexing`, then `indexed`. `GET /ingest-jobs/{id}` returns the same job.

Chunks land in `kb_chunks`. Each payload has `product_id`, `source_url`, and `text`. The dense vector is a local hash, so indexing needs no model key. The sparse vector stores term counts, and Qdrant applies an IDF modifier. Hybrid search fuses the two with reciprocal rank fusion.

## Product config

`POST /products` stores the config. `GET /products/{id}` reads it. `PUT /products/{id}` replaces it. A blank field is rejected. The description must be one paragraph.

The web app at `/` creates a product. `/products/{id}` edits the four fields and uploads files for that id. A saved config shows the word Saved.

`render_system_prompt` in `services/agent` includes the name, description, tone, and refusal rules.

## Live session

`POST /sessions` with `{"product_id":"<uuid>"}` returns `url`, `token`, and `room`. The token lets the browser join that room and publish the microphone and the screen. The API dispatches the agent named `kb-support` with job metadata `{"product_id":"<uuid>"}`. Missing LiveKit settings return 503.

The worker loads that product from `GET /products/{id}` and uses it as the system prompt. On a `*.livekit.cloud` URL it uses LiveKit Inference. On any other URL, including the Compose hostname `livekit`, it uses the OpenAI plugin and `OPENAI_API_KEY`.

Each product question calls `search_kb` against `kb_chunks`, filtered by `product_id`. The agent container reads `QDRANT_URL` (`http://qdrant:6333` in Compose). A matching passage is cited in the transcript. No matching passage produces `That is not in the docs.`

The worker subscribes to screen-share video when the browser publishes one. Each STT, LLM, and TTS metric is one JSON line on stdout, and each user or assistant turn is another JSON line with the per-turn delays. A knowledge lookup is another JSON line with `kind` set to `retrieval` and `duration_ms`.

The web app links to `/products/{id}/session`. Start session asks for the microphone and the screen, then plays the agent with `RoomAudioRenderer`.

## Checks

GitHub Actions (`.github/workflows/ci.yml`) runs, on pull requests and on pushes to `main`:

- web lint, typecheck, unit tests, and `pnpm build`
- Python lint, format check, typecheck, and unit tests
- offline evals via `make eval`, failing when a score is below `evals/thresholds.json`
- `docker compose config`
- a gitleaks scan

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

`.env.example` is placeholders. Do not commit `.env`, API keys, or live database passwords.

## License

MIT. The text is in `LICENSE`.
