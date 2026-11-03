# 0004: Desktop actions

Status: accepted

## Context

The support agent can see the user's screen share and talk. It cannot touch the user's computer. We want it to propose a click, a keystroke, or a scroll, and to do it only after the user says yes.

## Decision

### The Live model proposes, Computer Use plans, a helper acts

The voice model is a Gemini Live model. The Gemini Computer Use tool page lists `gemini-4-argon`, `gemini-3.8-flash`, `gemini-3.5-flash-lite`, and `gemini-3-flash-preview`. It does not list a Live model. So the Live agent exposes a tool, and that tool calls `gemini-3.8-flash` with the desktop environment (`ENVIRONMENT_DESKTOP`) to turn a request into an action. Source: https://ai.google.dev/gemini-api/docs/computer-use.

The agent already receives the screen share video, so the helper takes no screenshots. The user has to share the entire screen. A window share would put the model's coordinates on a different rectangle than the one the helper clicks.

### LiveKit RPC, not MCP, for the last hop

The helper joins the same room as the agent. The agent calls it with LiveKit RPC. The room already authenticates both sides, delivers the call in the same session, and ends it when the session ends. An MCP server would need its own transport, its own auth, and a way to find the user's laptop from a cloud worker. RPC payloads are small JSON strings, 15 KiB at most.

### Every action is approved in the web page

The agent never calls the helper on its own. The page shows each proposed action and the user approves it. Computer Use can return `safety_decision` `require_confirmation`. That case always needs an approval, whatever other setting is on. The tool that wires this lives in the agent and the page, not in the helper.

### What the helper checks

- It answers only a participant of kind `AGENT`. A user, the browser, and any other helper are refused.
- It validates every payload before it acts. Coordinates, text length, scroll size, and key names are bounded. An unknown field is an error.
- `--dry-run` logs the action and the point it maps to, and posts nothing.
- It runs one action at a time. Ctrl-C leaves the room and exits.

### Contract

Coordinates are on the 0..999 grid used by Gemini Computer Use. The helper maps `x * width // 1000` and `y * height // 1000` onto the main display in logical points. On a Retina screen logical points are not pixels, so no scale factor is applied. `desktop.info` reports `width`, `height`, and `scale`.

| Method | Payload | Reply |
| --- | --- | --- |
| `desktop.info` | none | `{"width", "height", "scale"}` |
| `desktop.click` | `{"x", "y", "button": "left" or "right", "double": bool}` | `{"ok": true}` |
| `desktop.type` | `{"text"}`, 1 to 500 characters | `{"ok": true}` |
| `desktop.key` | `{"keys": ["cmd", "shift", "t"]}`, modifiers plus one key | `{"ok": true}` |
| `desktop.scroll` | `{"x", "y", "dy", "dx"}`, lines from -50 to 50, positive is down and right | `{"ok": true}` |

Errors are RPC errors. Code 4000 is a bad payload, 4001 is a caller that is not the agent, and 4002 is a failure while acting. The message says what to fix.

### Token

`POST /sessions/{room}/desktop-token` is for a signed-in user whose own session it is. It returns `{url, token}`. The identity is `desktop:<user_id>`. The grant is room-scoped, can publish nothing, can subscribe to nothing, and can send data, which is what RPC needs. It lasts ten minutes. A token only matters at join time, so a running helper is not cut off.

### Permissions

macOS has to allow the terminal that starts the helper under System Settings > Privacy & Security > Accessibility. The helper checks this at start, prints that path, and exits with a non-zero status when it is missing. Screen recording is not needed.

## Limits

- The helper trusts the agent. It cannot see whether the user approved. A broken agent could act without approval. A later change can have the helper ask the page itself.
- Key codes follow the US layout. A shortcut on another layout can press a different key. Typed text goes in as Unicode and does not depend on the layout.
- Only the main display is controlled. A shared secondary screen does not line up.
- Scroll direction and horizontal scroll were not tried on a live window. No test posts an event.
- A new agent participant in the room is trusted like `kb-support`. Only `kb-support` is dispatched today.
- The agent worker may treat the helper as a user to listen to when it joins first. The tool that wires this has to pin the agent to the user's identity.

## Addendum, 2026-11-03: the agent tool, approvals, screenshots, and the cursor

The agent tool and the approval step are built. Three decisions above changed: the helper now takes screenshots, it needs Screen Recording, and the agent pins the user's identity.

### The loop

`operate_computer(goal)` on `SupportAgent` is available only when the dispatch named a signed-in user (`user:<id>`) and `desktop:<id>` is in the room. Otherwise it tells the model to guide with `point_at`. The prompt has the agent say what it will do and ask before it calls the tool.

1. The agent searches the docs for the goal through `POST /internal/search` and passes the passages as reference text.
2. The helper sends a screenshot. `gemini-3.8-flash` with `ComputerUse(environment=ENVIRONMENT_DESKTOP)` and a custom `yield_to_user` function returns the next call. The predefined actions the helper cannot run (`triple_click`, `middle_click`, `mouse_down`, `mouse_up`, `move`, `drag_and_drop`, `key_down`, `key_up`) are excluded. Other unknown calls go back to the model as an error.
3. The agent publishes an `ActionProposal` on the `computer` topic, audits it, and moves the cursor to `about-to-click`.
4. It waits up to 60 seconds for a `Decision` on `computer-decision`: `once`, `task` (allow the rest of this task), or `stop`. Only the participant named in the dispatch counts. A message from anyone else, a malformed one, or one for a proposal this task did not make is ignored.
5. On approval it publishes a `clicking` point on `hud`, sets the native cursor to `clicking`, calls the helper, and sends the result to the model with a fresh screenshot.
6. It stops on `yield_to_user`, `stop`, a timeout, a blocked safety decision, an error, or after ten model turns. It then hides the cursor and publishes `ended`.

A call whose `safety_decision` is `require_confirmation` always waits for the user, even after `task`, and the tray shows the explanation. The function response then carries `safety_acknowledgement: true`. A decision containing `block` ends the task.

Each proposal, decision, performed or failed action, and the end is written through `POST /internal/desktop-actions` to the audit log as `desktop.<event>` on the session. If the API does not record a step, the task stops before it acts.

The proposal's answer slot exists from the moment it is published. A live run showed the user can answer while the agent is still auditing and moving the cursor, and that answer was lost when the slot was made only on wait.

### Coordinates

The Computer Use page says both "pixel coordinates" and "normalized 1000x1000". A live call settled it: on the 1280 by 720 billing fixture, the model returned `click(x=322, y=528)` for the Update card button centred at 412, 380, which is 322 and 528 on a 0 to 999 grid. The proposal sends `x / 1000` and `y / 1000` to the page. The helper maps the grid to logical points as before.

### Screenshots

The agent's video frames come from the browser's screen share at a sampled rate and resolution, and the share may be a window. Computer Use needs the full display at the moment of each step, so the helper captures it with ScreenCaptureKit, scaled to fit 1440 by 900 (the size the Computer Use page recommends) and never up. An RPC reply holds at most 15 KiB, so `desktop.screenshot` takes a `stream_id` from the agent and sends the PNG to the caller as a LiveKit byte stream with that id. The agent accepts a stream only from the helper's identity. The capture leaves out the helper's own windows, so the model does not see the cursor overlay.

The helper now needs Screen Recording. It checks with `CGPreflightScreenCaptureAccess`, which asks nothing, and when it is missing it calls `CGRequestScreenCaptureAccess` once, prints the path, and exits 1.

### The cursor on the real screen

`desktop.cursor` sets the native cursor: a borderless, click-through window at overlay level, on every space, with sharing type none. `cursor.py` computes each frame (glide, pulse, ripple, and the time each state stays up) without AppKit, and `overlay.py` draws it. The asyncio loop runs on the main thread and pumps AppKit at 60 frames a second, so there is no second thread. The web cursor gained the same two states: `about-to-click` comes from a pending proposal and stays until the user decides, and `clicking` comes from a `hud` message and fades like a point.

### Who the agent listens to

`POST /sessions` now sends `{"product_id", "user"}` as dispatch metadata, where `user` is the token identity. The worker passes it as `RoomOptions(participant_identity=...)`, so a helper that joins first is never taken for the user, and the same identity is the only one whose decisions count.

### The flaky live test

The test sometimes failed with 4001 for the agent itself. The server announces a joining participant once its connection is up, which took 3.0 s on a local dev server in six runs out of six, and the agent's first RPC arrived before that. The helper now waits up to 5 s for an unknown caller before refusing. Ten runs in a row passed after the change.

## Limits after the addendum

- The helper still trusts the agent. A broken agent could act without approval. Having the helper ask the page would close that.
- The screenshot capture and the native overlay have not run against a real screen in CI or in development without Screen Recording. Their drawing and PNG encoding are tested off screen.
- Every screenshot of a task stays in the model's context. Ten steps is about eleven images.
- A browser that shares the screen with ScreenCaptureKit may still show the overlay in the preview.
