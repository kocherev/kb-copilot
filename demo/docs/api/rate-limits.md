# API rate limits

Rate limits protect the API from overload. Limits are counted per workspace, across all API keys.

## Limits by plan

The Team plan allows 600 requests per minute. The Enterprise plan allows 3,000 requests per minute. Starter workspaces do not have API access.

## Headers

Every response includes three headers. X-RateLimit-Limit is your limit per minute. X-RateLimit-Remaining is how many requests are left in the current window. X-RateLimit-Reset is the time, in seconds since the Unix epoch, when the window resets.

## When you go over

A request over the limit gets HTTP status 429. The response has a Retry-After header with the number of seconds to wait. Wait at least that long before you try again, and spread retries out instead of sending them all at once.

## Export endpoints

The bulk export endpoints have their own limit of 10 requests per hour. They do not count toward the per-minute limit.

## Temporary increases

Enterprise customers moving a large amount of data can ask support for a temporary increase. Increases last up to 7 days.
