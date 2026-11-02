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
