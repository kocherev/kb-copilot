# Verify webhook requests

Every webhook request is signed so your server can check that it really came from Northstar Desk.

## Signing secret

Each endpoint has its own signing secret. The secret is shown only once, when you create the endpoint, so store it in your secret manager right away.

## Check the signature

Each request carries an X-Northstar-Signature header. Its value is an HMAC SHA-256 of the raw request body, made with the signing secret and written as hexadecimal. Compute the same HMAC on your side and compare the two values with a constant-time comparison. Use the raw body exactly as received. Parsing the JSON and serializing it again changes the bytes and breaks the check.

## Stop replayed requests

Each request also has an X-Northstar-Timestamp header. Reject any request whose timestamp is more than 5 minutes old, even if the signature matches.

## Rotate the secret

Choose Rotate secret on the endpoint to get a new signing secret. The old secret keeps working for 24 hours after rotation, so you can deploy the new one without dropping requests.

## Source addresses

Deliveries come from a fixed list of IP addresses shown on the webhooks settings page. You can add them to your firewall allowlist, but always verify the signature as well.
