# Setup

More ways to run the stack after the Quickstart in the [README](../README.md#quickstart).

## Use LiveKit Cloud instead

Leave out `--profile livekit`. In `.env`, set `LIVEKIT_URL`, `LIVEKIT_AGENT_URL` and `LIVEKIT_API_URL` to the same `wss://<project>.livekit.cloud` URL, and set that project's `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET`. `GOOGLE_API_KEY` is still required, because the model call goes to Google and not through LiveKit.

```bash
docker compose up --build
```

The browser joins `LIVEKIT_URL`. The agent container joins `LIVEKIT_AGENT_URL`. The API dispatches the agent through `LIVEKIT_API_URL`. On the self-hosted profile these are three different addresses (`ws://localhost:7880`, `ws://livekit:7880`, `http://livekit:7880`), because `localhost` inside a container is not the LiveKit server.

## Change host ports

Compose reads these from `.env`. Postgres and Qdrant bind to `127.0.0.1` only.

| Variable | Default | Also change |
| --- | --- | --- |
| `WEB_PORT` | 3000 | `BETTER_AUTH_URL`, `CORS_ORIGINS`, and `LINEAR_REDIRECT_URI` if you use Linear |
| `API_PORT` | 8000 | `NEXT_PUBLIC_API_URL`, then rebuild the web image with `--build` |
| `POSTGRES_PORT` | 5432 | `DATABASE_URL`, which is for commands on the host |
| `QDRANT_PORT` | 6333 | `QDRANT_URL`, which is for commands on the host |
| `LIVEKIT_PORT`, `LIVEKIT_TCP_PORT`, `LIVEKIT_UDP_PORT` | 7880, 7881, 7882 | `LIVEKIT_URL`. Media needs the default UDP port 7882 |

Inside Compose the web server calls the API at `API_INTERNAL_URL`, which Compose sets to `http://api:8000`. To run two stacks side by side, also give the second one its own project name with `docker compose -p <name>`.

## Use the API from the command line

The web app signs you in with Better Auth and sends the API a short-lived JWT (15 minutes). You can do the same from a shell. Sign up, keep the session cookie, and read the token:

```bash
curl -s -c cookies.txt -H 'content-type: application/json' \
  -d '{"name":"You","email":"you@example.com","password":"choose-a-long-password"}' \
  http://localhost:3000/api/auth/sign-up/email
TOKEN=$(curl -s -b cookies.txt http://localhost:3000/api/auth/token | sed -E 's/.*"token":"([^"]+)".*/\1/')
```

Create a product, upload documents as multipart form data, and list them:

```bash
ID=$(curl -s -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"name":"Northstar Desk","description":"Northstar Desk is a help desk for support teams.","tone":"calm and brief","refusal_rules":"Do not invent a policy."}' \
  http://localhost:8000/products | sed -E 's/.*"id":"([^"]+)".*/\1/')
curl -s -H "authorization: Bearer $TOKEN" \
  $(for f in demo/docs/billing/*; do printf -- '-F files=@%s ' "$f"; done) \
  http://localhost:8000/products/$ID/documents
curl -s -H "authorization: Bearer $TOKEN" http://localhost:8000/products/$ID/documents
```

The upload returns 202 and a job. The list shows each document with `status` (`queued`, `indexing`, `indexed`, or `failed`), `chunk_count`, and `error`. A file name that already exists replaces the old document. Delete one with `DELETE /products/$ID/documents/<document id>`.

For a script that outlives 15 minutes, create an organization API key with the JWT and send it the same way. The secret starts with `kb_`, is shown once, and only its hash is stored.

```bash
curl -s -X POST -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"name":"ci"}' http://localhost:8000/api-keys
```

`scripts/smoke.py` walks the same flow against a running stack, including the agent's first reaction in the room. `API_PORT` and `WEB_PORT` pick the host ports, as in Compose. The full route list is in `apps/web/openapi.json`.
