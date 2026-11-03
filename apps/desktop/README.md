# Desktop helper

`kb-desktop` is a macOS program that joins a support session's LiveKit room and performs mouse and keyboard actions on your computer when the agent asks over LiveKit RPC. It takes no screenshots. The agent already sees your screen share.

The agent does not call it yet. `services/agent` has two tools, `search_kb` and `point_at`, and neither uses the helper. The web page has no approval step either. Today the helper joins a room and answers RPC calls from any participant of kind agent. The design, including the planned Computer Use tool and per-action approval, is in `docs/decisions/0004-desktop-actions.md`.

## Run

You need macOS, Python 3.12, uv, and a running stack with a session (see the Quickstart in the repository README).

1. Start a session in the web app so a room exists.
2. Sign in from a shell and read a token, as in "Use the API from the command line" in the repository README. The next steps use `$TOKEN`.
3. Ask the API for the room of your latest session, then for a desktop token for that room:

```bash
ROOM=$(curl -s -H "authorization: Bearer $TOKEN" http://localhost:8000/sessions | grep -o '"room":"[^"]*"' | head -1 | cut -d'"' -f4)
curl -s -X POST -H "authorization: Bearer $TOKEN" http://localhost:8000/sessions/$ROOM/desktop-token
```

The reply is `{"url": "...", "token": "..."}`. The token is for your own session only, grants RPC and nothing else, and works for ten minutes.

4. From the repository root, start the helper with that URL and token:

```bash
uv run --package kb-desktop kb-desktop --url <url> --token <token>
```

Press Ctrl-C to leave the room and exit.

| Flag | Meaning |
| --- | --- |
| `--url` | LiveKit `ws://` or `wss://` URL from the token reply |
| `--token` | Token from `POST /sessions/{room}/desktop-token` |
| `--dry-run` | Join and answer calls, log each action and the point it maps to, and perform nothing. Skips the Accessibility check |

Try `--dry-run` first. It prints `joined <room> as desktop:<user id>` once the helper is in the room.

## macOS permissions

The helper posts mouse and keyboard events, which macOS allows only for apps with Accessibility access. Under System Settings > Privacy & Security > Accessibility, switch on the terminal you start `kb-desktop` from (Terminal, iTerm, or VS Code). Without it the helper prints that path and exits with status 1.

The helper does not capture the screen, so it does not need Screen Recording. The browser that shares your screen with the agent does, and macOS asks for it the first time.

## What it accepts

It answers five RPC methods, and only from a participant of kind agent. A call from a user, the browser, or another helper is refused with code 4001. Coordinates are on the 0 to 999 grid that Gemini Computer Use uses, mapped onto the main display. Any other field, or a value out of range, is refused with code 4000. A failure while acting is code 4002.

| Method | Payload | Reply |
| --- | --- | --- |
| `desktop.info` | none | `{"width", "height", "scale"}` of the main display |
| `desktop.click` | `{"x", "y", "button": "left" or "right", "double": bool}` | `{"ok": true}` |
| `desktop.type` | `{"text"}`, 1 to 500 characters | `{"ok": true}` |
| `desktop.key` | `{"keys": ["cmd", "shift", "t"]}`, modifiers plus one key | `{"ok": true}` |
| `desktop.scroll` | `{"x", "y", "dy", "dx"}`, lines from -50 to 50, positive is down and right | `{"ok": true}` |

It runs one action at a time.

## Limits

- Only the main display is controlled, so share the entire main screen.
- Key codes follow the US keyboard layout. Typed text is sent as Unicode and does not depend on the layout.
- The helper cannot tell whether a person approved an action. Until the agent tool and the approval step exist, treat a running helper as trusting the agent.
- No test posts a real mouse or keyboard event. `uv run pytest apps/desktop/tests` covers payload validation, the caller check, the RPC handlers, and the coordinate mapping. With `KB_DESKTOP_LIVE=1` and a LiveKit server, it also runs a dry-run round trip through the room.
