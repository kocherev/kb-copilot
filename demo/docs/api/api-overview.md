# API overview

The Northstar Desk REST API lets you read and change tickets, contacts, and users from your own code. The API is included in the Team and Enterprise plans. Starter workspaces cannot use it.

## Base URL and format

All requests go to https://api.northstardesk.example/v2. Requests and responses use JSON. Timestamps are ISO 8601 strings in UTC.

## Authentication

Send an API key in the Authorization header as a bearer token. Keys are created by Admins, as the API keys page explains. Every request must use HTTPS. Plain HTTP requests are refused.

## Safe retries

For POST requests, send an Idempotency-Key header with a unique value. If you repeat the request with the same key, Northstar Desk returns the first result instead of creating a second record. Idempotency keys are remembered for 24 hours.

## Versions

The current version is v2. Version 1 was retired on 31 March 2026, and requests to v1 now return an error. We announce breaking changes in the changelog at least 6 months ahead.

## Limits

Each workspace has a request limit per minute that depends on the plan. The rate limits page explains the limits and the headers that report them.
