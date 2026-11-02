# Troubleshoot integrations and the API

Use this page when Slack alerts stop, webhooks fail, or API calls return errors.

## Slack alerts stopped

The most common cause is that someone removed the @Northstar bot from the channel. Invite the bot back. If alerts stopped for every channel, open Settings > Integrations > Slack and choose Reconnect. A reconnect is needed when the Slack admin who approved the app removes it.

## Webhook signature does not match

Compute the HMAC over the raw request body before parsing the JSON. Make sure you use the secret of that endpoint, and remember that after a rotation the old secret only works for 24 hours.

## Webhook endpoint was disabled

An endpoint is disabled after 50 failed deliveries in a row. Check your server logs for slow responses: an answer that takes longer than 10 seconds counts as a failure.

## API returns 401 or 403

A 401 means the key is missing, revoked, or expired. A 403 means the key's scope is too small for the request, for example a read key trying to update a ticket.

## API returns 429

You went over the rate limit. Wait for the number of seconds in the Retry-After header before you send more requests.
