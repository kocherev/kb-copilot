---
name: livekit-agent
description: >
  Change the LiveKit support worker: dispatch, screen share, the search_kb
  tool, citations, and voice providers. Use when editing services/agent or
  POST /sessions.
---

# LiveKit agent

The worker is `services/agent`. The browser session is `apps/web`. The token and the dispatch are `services/api`.

## Dispatch

The agent name is `kb-support` in both `services/agent/src/kb_agent/worker.py` and `services/api/src/kb_api/sessions.py`. `POST /sessions` sends job metadata `{"product_id":"<uuid>"}`. A missing product returns 404 and does not dispatch. Missing LiveKit settings return 503.

The worker reads `product_id` from that metadata and loads the system prompt with `GET /products/{id}`. `render_system_prompt` includes the name, description, tone, and refusal rules. Config is data. Do not hard-code a product.

## Retrieval and citations

On a user turn with content words, the worker calls `search_kb` before the model speaks. The tool of the same name is for a follow-up query. Both call `packages/rag` through the in-process helper, filtered by `product_id`.

- Hits are remembered and appended to the transcript as `Source: <source_url>`, one line per source.
- No hit yields exactly `That is not in the docs.` The model is not called for that turn.
- The system prompt says not to read source URLs aloud. The transcript lists them.
- The web parser in `apps/web/src/lib/session.ts` and the scorer in `evals` depend on that `Source:` line. Change the three together.
- A lookup logs one JSON line: `kind` is `retrieval`, plus `product_id`, `duration_ms`, and `hit_count`.

`QDRANT_URL` defaults to `http://localhost:6333`. Compose sets `http://qdrant:6333` on the agent.

## Room and screen

The browser publishes the microphone and the screen, not the camera. `sessionPublish` in `apps/web/src/lib/session.ts` is that contract.

`session_room_options` turns video input on so the worker can subscribe to screen-share video. `watch_screen_share` logs `{"event":"screen_share","subscribed":true}` when the track source is screen share and the kind is video.

On a Cloud host those frames are pushed into the realtime model. The OpenAI pipeline does not consume them. The page draws a highlight from `hud` messages (`point_at`) and a Thinking label from agent state. That overlay stays in the browser. It does not move the operating-system pointer.

## Voice

`build_voice` picks the provider from `LIVEKIT_URL`.

- Host `livekit.cloud` or `*.livekit.cloud`: LiveKit Inference realtime. The model id is `google/gemini-3.8-live-extended-thinking`, voice `Puck`, reasoning effort `low`. If `session.start` fails, try `google/gemini-3.8-live`, then `google/gemini-live`. `OPENAI_API_KEY` can stay empty. Client VAD commits the turn so `search_kb` still runs before the reply. A miss speaks `That is not in the docs.` through the Inference TTS and does not ask the realtime model to answer.
- Any other host, including Compose `livekit`: the OpenAI plugin. Set `OPENAI_API_KEY`. Screen frames are not sent to that model.

STT, LLM, TTS, and realtime metrics are JSON lines on stdout (`kind` `component`). A realtime line can include `image_tokens`. Each user or assistant turn adds a line with the per-turn delays.

The container command is `python -m kb_agent start`. It exits when `LIVEKIT_URL` or the key pair is missing. The dev server in the `livekit` Compose profile does not read the env file. Its key pair is `devkey` / `secret`. The browser uses `LIVEKIT_URL`. The agent container uses `LIVEKIT_AGENT_URL`.

## Checks

```bash
uv run pytest services/agent/tests services/api/tests/test_sessions.py
```

A change to citation text or retrieval also needs `make eval`. Paste the table when you open the pull request. See `skills/prove-it-works/SKILL.md`.
