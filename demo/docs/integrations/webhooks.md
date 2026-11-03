# Webhooks

Webhooks send an HTTP request to your server when something changes in Northstar Desk. They are available on the Team and Enterprise plans.

## Add an endpoint

An Admin opens Settings > Integrations > Webhooks and chooses Add endpoint. The endpoint URL must use HTTPS. Pick the events the endpoint should receive. The Team plan allows 20 endpoints, and Enterprise allows 100.

## Events

Northstar Desk sends four events: ticket.created, ticket.updated, ticket.solved, and comment.added. Each request is a POST with a JSON body that contains the event name, a delivery ID, and the ticket.

## Responding to deliveries

Your endpoint must answer with a 2xx status code within 10 seconds. Any other status code, or a slower answer, counts as a failed delivery.

## Retries

A failed delivery is retried up to 6 times over 24 hours, with the wait between attempts growing each time. The delivery ID stays the same across retries, so you can ignore duplicates.

## Disabled endpoints

After 50 failed deliveries in a row, the endpoint is disabled and every Admin gets an email. Fix the problem, then turn the endpoint back on from the webhooks page. Deliveries missed while it was disabled are not resent.
