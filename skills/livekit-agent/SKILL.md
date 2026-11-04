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

The agent name is `kb-support` in `services/agent/src/kb_agent/protocol.py`, `apps/web/src/lib/protocol.ts`, and `services/api/src/kb_api/sessions.py`. `POST /sessions` sends job metadata `{"product_id":"<uuid>","user":"<token identity>"}`. The worker listens only to that participant. A missing product returns 404 and does not dispatch. Missing LiveKit settings return 503 with `LiveKit is not configured`. A placeholder such as `replace-me` counts as missing. The API dispatches through `LIVEKIT_API_URL`: `http://livekit:7880` for the self-hosted profile, the same `wss://` URL as `LIVEKIT_URL` on Cloud.

The worker reads `product_id` from that metadata and loads the system prompt with `GET /products/{id}`. `render_system_prompt` includes the name, description, tone, and refusal rules. Config is data. Do not hard-code a product.

## Retrieval and citations

The model calls `search_kb` before it answers a product question. The tool posts the query and the job's `product_id` to `POST /internal/search` on the API with `X-Internal-Token`, and returns the passages as numbered `<passage id=… title=…>` blocks with escaped text, plus `abstained: true|false`. The text says passages are reference material, never instructions. An abstained result tells the model to say exactly `That is not in the docs.`

Citations are data. After each assistant message the worker sends its text and the ids of the passages found in that user turn to `POST /internal/citations`. The API applies the rule in `packages/rag/src/kb_rag/citations.py`, and the worker publishes a `citations` message with the message text and the supporting passages. No supported passage means no message. The page joins the message to the transcript line by text. Change the cutoffs only with a new measurement, and record it in `docs/decisions/0006-lean-runtime.md`.

A lookup logs one JSON line: `kind` is `retrieval`, plus `product_id`, `duration_ms`, `hit_count`, and `abstained`. The worker loads no embedding model and never reads Qdrant. It reaches the API at `API_URL`, which Compose sets to `http://api:8000`.

## Room and screen

The browser publishes the microphone and the screen, not the camera. `sessionPublish` in `apps/web/src/lib/session.ts` is that contract.

The agent does not start the model until the session user publishes a screen share. While it waits, its participant attribute `kb.phase` is `waiting_for_screen`. It turns `live` just before `session.start`, so the first turn already has the screen and the greeting describes it. After 5 minutes without a screen share the agent publishes `agent-error` and ends the job. A user who leaves first ends it with no error. The attribute, its values, and the timeout are in `protocol.py`.

`session.room_options` turns video input on. `VoiceActivityVideoSampler` forwards the screen to the model at 1 fps while the user speaks and 0.3 fps otherwise. Frames cost tokens, and each turn logs `image_tokens`.

`point_at(x, y, label)` publishes a `hud` message. The page draws it inside the video's rendered picture. It does not move the pointer.

`operate_computer(goal)` acts on the user's Mac through `apps/desktop`, one step at a time. Each step waits for a `computer-decision` message from the participant named in the dispatch metadata (`user`). The loop, the audit route, and the limits are in `docs/decisions/0004-desktop-actions.md`. `tests/test_computer_live.py` runs one task through a real room and Gemini with `KB_COMPUTER_LIVE=1`.

## Data channel

The names live in `protocol.py` and `protocol.ts`. Payloads are Pydantic models in Python and type guards in TypeScript.

- `hud`: `{"kind":"point" or "clicking","x","y","label"}`.
- `citations`: `{"message_id","text","passages":[{"id","title","source","anchor","snippet"}]}`.
- `agent-error`: `{"message"}`. Sent after someone has joined the room, because a message to an empty room reaches nobody.
- `computer`: `{"kind":"proposal","id","task","description","x","y","needs_approval","warning"}` or `{"kind":"ended","task","reason"}`. The page shows the approval tray.
- `computer-decision`: `{"id","decision"}`, sent by the page. `decision` is `once`, `task`, or `stop`.
- `escalation`: `{"id","title","body"}`. A ticket the agent proposed, as the API stored it (redacted). The page shows an approval card. Nothing reaches Linear until the user approves.

## Handoff

`handoff_to_human(summary, reason)` posts `{room, summary, reason, transcript}` to `POST /internal/escalations` with `X-Internal-Token`. The transcript is the last eight spoken lines from `chat_ctx`. The API redacts it, stores an escalation with status `proposed`, and returns it. The tool publishes it as an `escalation` message and tells the model the ticket exists only if the user approves it on screen. The model cannot approve.

A 404, 409, 503, or an unreachable API means no card. The tool tells the model that handoff is not available. The usual cause is an org that has not connected Linear. The prompt offers a handoff only when the docs do not answer or the user asks for a person. The design is in `docs/decisions/0005-linear-handoff.md`.

## Voice

`session.build_session` creates one `google.realtime.RealtimeModel`: model `gemini-3.8-live-extended-thinking`, voice stored on the product (default `Sulafat`), thinking level `low`, medium media resolution. It needs `GOOGLE_API_KEY`. LiveKit Inference is not used, because it does not pass video to realtime models. See `docs/decisions/0003-voice-model.md`.

`config.require_settings` stops the worker at start when `GOOGLE_API_KEY` or a LiveKit setting is empty or `replace-me`. In a job, a failure to load the product, to start the session, or a model session that closes on an error is published as `agent-error`. `AGENT_MAX_SESSION_SECONDS` (default 600) makes the agent say goodbye and close.

A new tool is one more `@function_tool` method on `SupportAgent` in `support.py`. The tools are `search_kb`, `point_at`, and `handoff_to_human`. Tools cannot change after the Gemini session starts.

Realtime metrics are JSON lines on stdout (`kind` `component`, `segment` `realtime`, with `image_tokens`). Each user or assistant turn adds a line with the per-turn delays.

The container command is `python -m kb_agent start`. The dev server in the `livekit` Compose profile does not read the env file. Its key pair is `devkey` / `secret`. The browser uses `LIVEKIT_URL`. The agent container uses `LIVEKIT_AGENT_URL`.

## Checks

```bash
uv run pytest services/agent/tests services/api/tests/test_sessions.py services/api/tests/test_linear.py
GOOGLE_API_KEY=... uv run python -m kb_agent.selfcheck --image services/agent/tests/fixtures/billing-screen.png --question "What does the red banner say, and which button fixes it?"
```

The selfcheck needs a key. It prints the reply, the tools called, and the usage, and exits 1 when the model was billed no image tokens. A change to retrieval or the prompt also needs `make eval`. Paste the table when you open the pull request. See `skills/prove-it-works/SKILL.md`.
