# Pagination and errors

This page covers how list endpoints return large results and what error responses look like.

## Cursor pagination

List endpoints return results one page at a time. Use the limit parameter to set the page size. The default page size is 25 and the largest allowed is 100. Each response includes a next_cursor value. Pass it as the cursor parameter to get the next page. When next_cursor is null, you have reached the last page.

## Error format

Errors return a JSON body with a code and a message. The code is a short machine-readable string such as invalid_scope. The message explains the problem in plain words.

## Common status codes

- 401 means the API key is missing, revoked, or expired.
- 403 means the key is valid but its scope does not allow the request.
- 404 means the record does not exist or is not in your workspace.
- 422 means the request body failed validation.
- 429 means you went over the rate limit.

## Server errors

A 5xx status means something went wrong on our side. Retry the request with a growing wait between attempts. For POST requests, reuse the same Idempotency-Key so a retry does not create a duplicate record.
