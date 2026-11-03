# Desktop helper

`kb-desktop` is a macOS program that joins a support session's LiveKit room. When the agent asks over LiveKit RPC, it sends a screenshot of the main display, draws the agent's cursor on the real screen, and clicks, types, presses keys, or scrolls.

The agent's `operate_computer` tool calls an action only after the user allows that step in the session page. The helper itself cannot see that approval, so it answers only the agent participant. The design is in `docs/decisions/0004-desktop-actions.md`.

## Run

You need macOS 14 or later, Python 3.12, uv, and a running stack with a session (see the Quickstart in the repository README).

1. Start a session in the web app and share your entire screen.
2. In the "Your Mac" panel under the preview, press Connect your Mac, then Copy command. The command holds a token for your own session. It grants RPC and data only and works for ten minutes.
3. From the repository root, run it. Add `--dry-run` the first time:

```bash
uv run --package kb-desktop kb-desktop --url <url> --token <token> --dry-run
```

It prints `joined <room> as desktop:<user id>` once it is in the room, and the panel then says your Mac is connected. Press Ctrl-C to leave the room and exit.

Without the web page, the same token comes from the API. Sign in from a shell as in "Use the API from the command line" in the repository README, then:

```bash
ROOM=$(curl -s -H "authorization: Bearer $TOKEN" http://localhost:8000/sessions | grep -o '"room":"[^"]*"' | head -1 | cut -d'"' -f4)
curl -s -X POST -H "authorization: Bearer $TOKEN" http://localhost:8000/sessions/$ROOM/desktop-token
```

| Flag | Meaning |
| --- | --- |
| `--url` | LiveKit `ws://` or `wss://` URL from the token reply |
| `--token` | Token from `POST /sessions/{room}/desktop-token` |
| `--dry-run` | Join, send screenshots, and draw the cursor. Log each action and the point it maps to, and perform nothing. Skips the Accessibility check |

## macOS permissions

Both permissions belong to the terminal app you start `kb-desktop` from (Terminal, iTerm, or VS Code), not to the helper.

| Permission | Why | Where |
| --- | --- | --- |
| Screen Recording | The agent plans each step from a screenshot | System Settings > Privacy & Security > Screen & System Audio Recording |
| Accessibility | Posting mouse and keyboard events. Not needed with `--dry-run` | System Settings > Privacy & Security > Accessibility |

Without Screen Recording the helper asks macOS once, which adds the terminal to the list switched off, prints the path, and exits with status 1. macOS applies the switch only after you quit and reopen the terminal. Without Accessibility the helper prints that path and exits with status 1.

## What it accepts

It answers seven RPC methods, and only from a participant of kind agent. A call from a user, the browser, or another helper is refused with code 4001. A caller the room has not announced yet gets up to 5 seconds to appear, because the server announces a participant once its connection is up, and an RPC can arrive first. Coordinates are on the 0 to 999 grid that Gemini Computer Use uses, mapped onto the main display. Any other field, or a value out of range, is refused with code 4000. A failure while acting is code 4002.

| Method | Payload | Reply |
| --- | --- | --- |
| `desktop.info` | none | `{"width", "height", "scale"}` of the main display |
| `desktop.screenshot` | `{"stream_id"}` | `{"bytes"}`. The PNG goes to the caller as a byte stream on topic `desktop.screenshot` with that stream id |
| `desktop.cursor` | `{"state", "x", "y", "name", "label"}`, state `thinking`, `about-to-click`, `clicking`, or `hidden` | `{"ok": true}` |
| `desktop.click` | `{"x", "y", "button": "left" or "right", "double": bool}` | `{"ok": true}` |
| `desktop.type` | `{"text"}`, 1 to 500 characters | `{"ok": true}` |
| `desktop.key` | `{"keys": ["cmd", "shift", "t"]}`, modifiers plus one key | `{"ok": true}` |
| `desktop.scroll` | `{"x", "y", "dy", "dx"}`, lines from -50 to 50, positive is down and right | `{"ok": true}` |

An RPC reply holds at most 15 KiB, so a screenshot travels as a LiveKit byte stream. It is the main display scaled down to fit 1440 by 900, the size Computer Use recommends, and never scaled up. The helper's own windows are left out of it.

The cursor is a small borderless window above everything else that ignores the mouse, so a click goes through to the app below. It glides to each target, pulses while a step waits for approval, ripples once on a click, and hides itself when the agent stops sending states. It asks macOS to keep it out of screen captures.

Actions run one at a time.

## Limits

- Only the main display is shown and controlled, so share the entire main screen.
- Key codes follow the US keyboard layout. Typed text is sent as Unicode and does not depend on the layout.
- The helper trusts the agent. The approval lives in the agent and the page.
- Browsers that capture the screen with ScreenCaptureKit on macOS 15 and later may ignore the request to hide the cursor window, so the preview can show it next to the page's own cursor.
- No test posts a real mouse or keyboard event or captures the real screen without Screen Recording. `uv run pytest apps/desktop/tests` covers payload validation, the caller check, the RPC handlers, the coordinate mapping, the cursor animation, PNG encoding, and drawing the cursor off screen. The capture test runs only when the terminal already has Screen Recording. With `KB_DESKTOP_LIVE=1` and a LiveKit server, a dry-run round trip goes through a real room, including a screenshot stream.
