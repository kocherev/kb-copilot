# 0007 Session replay

Status: accepted, 2026-11-03

## Context

A voice session is hard to review after it ends. The worker printed latency as JSON on stdout and kept no record of what was said, what it searched, or what it cited. A bad answer could not be traced to the passage that caused it, and a slow turn could not be traced to a stage.

## Decision

Every session leaves a replay in the product's own database. Tracing to an outside system is optional and off.

### What is recorded

The agent posts one record per turn to `POST /internal/turns` with `X-Internal-Token`. The API stores it in the `turns` table, keyed to the `live_sessions` row by room name. A record holds:

- the role (`user` or `assistant`) and the transcript text;
- when the turn started and ended, from the model's speaking times when it reports them;
- every search the agent ran for that answer: query, the passages that came back with their scores, whether it abstained, and how long the call took;
- the ids of the passages the answer cited;
- the stage timings LiveKit measures per turn: end of turn and transcript delay for a user turn, model first token, first audio and end to end time for an agent turn;
- the image tokens the model billed since the last agent turn, when it reports them.

Desktop actions are not copied. The API already writes an audit row for each step of a computer task (`desktop.proposed`, `approved`, `denied`, `timed_out`, `performed`, `failed`, `ended`), and a handoff is an `escalations` row. The replay joins both to the session. `GET /sessions` lists an org's sessions (optionally one product's) with turn, action and handoff counts. `GET /sessions/{id}` returns the session with its turns, desktop steps and handoffs. Both are scoped to the caller's org, and another org's session is a 404.

The web app shows the list on the product page and the replay at `/products/<id>/sessions/<session id>`: the transcript, each answer's searches and citations, the desktop steps, the handoffs, and a latency bar per turn.

### Sending never costs the conversation

The agent sends each record from a background task with a 2 s timeout. A failed or slow post is logged as `turn_record_failed` and dropped. Nothing retries, so a turn is lost when the API is down, and the voice loop never waits for it. The last records get 3 s to go out when the session ends.

The agent notes searches by wrapping its `Knowledge` object, not by changing the tools, so a new tool that searches is recorded too.

### Redaction

The API redacts a turn's text and each search query before it stores them, with the same patterns as the Linear handoff: email addresses, runs of 13 to 19 digits, and phone-like digit runs become `[email]`, `[card]` and `[phone]`. They are regular expressions. They miss a card number read out in words, and a name or an address. The replay also redacts the detail of each desktop step when it serves it, because the audit rows were written before this decision and hold what the agent reported. Treat the replay as sensitive: it is readable by anyone in the org.

### Retention

Turns stay until their session goes. A session goes when its product is deleted, which cascades. There is no purge job and no delete route for one session. Add an age limit if a deployment needs one.

### Tracing

Set `OTEL_EXPORTER_OTLP_ENDPOINT` and the agent hands LiveKit Agents' own session tracing an OTLP exporter, and the API instruments FastAPI the same way. With it unset the SDK, the exporter and the instrumentation are not imported. The agent passes `allow_pii=False`, so spans carry timings, models and token counts but not the conversation, and tags each span with the room and product. The replay page shows the room name. To find that session's traces in Jaeger, search for the tag `kb.room` with it.

Compose has an `observability` profile with Jaeger (`jaegertracing/jaeger`, one container, in-memory). It adds no service to the default stack.

## Why not a separate tracing service by default

- A tracing backend needs its own storage, retention and access control. The replay is in Postgres, behind the same org check as everything else.
- The two answer different questions. A trace shows where time went inside one request. A replay shows what was said and why, which a trace cannot show without carrying the conversation to another system.
- The default stack should run on a 16 GB laptop (see 0006). One more container is a choice, so it sits behind a profile.
- OTLP is the standard door. A deployment with Datadog, Honeycomb or Langfuse sets the endpoint and headers and needs no code change.

## Consequences

- One more write per turn, in a small table. A session of 20 turns adds 20 rows.
- Turn text is stored. A deployment that must not keep conversations needs a switch that does not exist yet.
- A turn is attributed by order of arrival at the agent. If the user speaks again before an answer's citation check finishes, a search can be filed under the wrong answer. The citation check takes tens of milliseconds, so this is rare.
- The latency bar draws a turn's stages end to end from the durations the agent measured. Stages that overlap make the bar longer than the end to end figure beside it, which is the one to read.
