# 0005: Linear handoff

Status: accepted, 2026-11-02

## Context

The agent answers from the docs. When they do not cover the question, or the user asks for a person, it should hand the problem to a human. The team already tracks work in Linear, so the handoff is a Linear issue.

## Decision

### OAuth, not a personal token

An org connects Linear with the OAuth authorization code flow (https://linear.app/developers/oauth-2-0-authentication). A personal API key belongs to one person, carries all of that person's access, never expires on its own, and would sit in an env file or a form field. An OAuth grant is made by clicking through Linear's own consent page, names its scopes, and can be revoked from either side. The app asks for `read` and `issues:create`. `read` is on every grant and loads the workspace and team. `issues:create` is the only write the app does.

Linear access tokens last 24 hours. The grant includes a refresh token, and Linear rotates it on each use. The API refreshes an expired access token before it creates an issue, stores the new pair, and asks the user to reconnect when the refresh fails.

The tickets are created as the user who connected. Creating them as the app (`actor=app`) is an option for later.

### The flow

1. The user opens Settings and presses Connect Linear. The page calls `GET /integrations/linear/connect` with its bearer token and gets the authorize URL. It cannot be a redirect, because a browser navigation carries no bearer header.
2. Linear sends the browser to `/api/integrations/linear/callback` in the web app. This path is the registered redirect URI and has to stay as it is. The route runs on the server with the user's session, and forwards `code` and `state` to `POST /integrations/linear/callback`.
3. The API checks the state, exchanges the code at `https://api.linear.app/oauth/token`, reads the organization name and the first team through GraphQL, and stores the connection. One connection per org. Connecting again replaces it.
4. The route redirects to `/settings?linear=connected`, `denied`, or `failed`.

`DELETE /integrations/linear` asks Linear to revoke the grant, then deletes the row. A failed revoke is logged and does not block the delete.

### State

The `state` value is `base64url(claims).base64url(HMAC-SHA256)`. The claims are the org, the user, a random nonce, and an expiry ten minutes out. The callback accepts it only when the signature holds, the expiry has not passed, the org and user match the signed-in caller, and the nonce has not been seen. The nonce is recorded in `linear_state_uses` before the code is exchanged, so a replay fails even when the first attempt failed. A state copied to another user or org is refused. The HMAC key is derived from `LINEAR_TOKEN_KEY`.

### Tokens at rest

Access and refresh tokens are stored as AES-GCM ciphertext with a random 12-byte nonce. The associated data is the org id, so a row copied to another org does not decrypt. The key is `LINEAR_TOKEN_KEY`, 32 random bytes in base64. A missing or `replace-me` key, client id, or client secret turns the feature off: `GET /integrations/linear` reports `enabled: false`, and the other routes return 503 and name what to set. A key that is not 32 bytes of base64 is also a 503. Losing the key makes stored tokens unreadable, and each org has to reconnect.

### Approve before write

The agent calls `handoff_to_human(summary, reason)`. The tool posts to `POST /internal/escalations` with the internal token, and the API stores an escalation with status `proposed`. The agent publishes an `escalation` data message with the stored id, title, and body. The session page shows a card with Approve and Dismiss. Only `POST /escalations/{id}/approve`, called with the user's token from the same org, calls Linear's `issueCreate`. `dismiss` never calls Linear.

The API takes only the room name from the agent and finds the org and product from the live session row. A room the API did not start is a 404.

Approve claims the row with a conditional update from `proposed` to `creating`, so a double click or two tabs create one issue. If the request dies after the claim, the row stays `creating`. Once it has not changed for 2 minutes, a new approve can claim it with a conditional update that renews the lease, create the issue, and move it to `created`. A `creating` row that changed more recently still counts as in progress and answers 409 without calling Linear. A second approve of a created escalation returns the same issue. A failed `issueCreate` puts the row back to `proposed` and answers 502, so the user can try again. Approving a dismissed escalation, or dismissing a created one, is a 409.

Every step writes an audit row: `linear.connect`, `linear.disconnect`, `escalation.propose` (actor `agent`), `escalation.approve`, `escalation.approve_failed`, and `escalation.dismiss`.

Without a connection the API answers 409 to the proposal, the tool tells the model that handoff is not available, and the page shows no card.

### Redaction

The body is the summary, the product name, the reason, and the last eight spoken lines, each cut to 400 characters. The API redacts the title and body before it stores them, so neither the database, the card, nor Linear holds the raw text. Email addresses, runs of 13 to 19 digits (card numbers), and phone-like digit runs become `[email]`, `[card]`, and `[phone]`. The patterns are regular expressions. They miss a card number read out in words and a name or address. The card shows what will be sent, which is the user's check.

## Failure modes

| Case | What happens |
| --- | --- |
| Linear settings missing | Settings says what to set. The agent tool says handoff is unavailable. |
| User denies consent | The callback redirects with `linear=denied`. The API is not called. |
| State tampered, expired, replayed, or for another user | 400. No token request is made. |
| Linear refuses the code | 502. Nothing is stored. |
| Workspace has no teams | 502. Nothing is stored. |
| Access token expired, refresh fails | Approve answers 409 and asks for a reconnect. The escalation stays `proposed`. |
| Linear is down on approve | 502. The escalation stays `proposed`. |
| Disconnect while a card is open | Approve answers 409. |

## Limits

- The tickets go to the first team Linear returns. There is no team picker.
- The agent is not told when the user approves. The page shows the ticket number.
- A card is kept in the page only. After a reload an open proposal stays `proposed` in the database and cannot be approved from the page.
- Any member of an org can connect or disconnect Linear. Org admins are not modeled.
- The agent does not limit how many proposals it makes in one session.

## Setup

1. Create an OAuth2 app at https://linear.app/settings/api. Set the callback URL to `http://localhost:3000/api/integrations/linear/callback`, or to `<your web URL>/api/integrations/linear/callback` and the same value in `LINEAR_REDIRECT_URI`.
2. Put the client id and secret in `.env` as `LINEAR_CLIENT_ID` and `LINEAR_CLIENT_SECRET`.
3. Generate the key: `openssl rand -base64 32`, and set `LINEAR_TOKEN_KEY`.
4. Open Settings in the web app and press Connect Linear.

`KB_LIVE_LINEAR=1 uv run pytest services/api/tests/test_linear_live.py -s` creates one `[kb-copilot test]` issue in the first team of `LINEAR_API_KEY` (a personal key), prints its identifier, and archives it.
