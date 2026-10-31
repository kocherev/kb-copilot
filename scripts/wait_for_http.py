"""Wait until an HTTP endpoint returns status 200.

Qdrant `GET /readyz` answers with plain text (`all shards are ready`), not JSON.
This script checks the status code and leaves the body unread as data.
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request


def is_ready(status_code: int, body: str) -> bool:
    """Return true when the response status is 200.

    `body` is part of the signature so callers pass the payload through.
    The function does not parse it.
    """
    del body
    return status_code == 200


def wait_for_http(url: str, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while True:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                raw = response.read().decode("utf-8", errors="replace")
                if is_ready(response.status, raw):
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args(argv)
    if wait_for_http(args.url, args.timeout):
        return 0
    print(f"timed out waiting for HTTP 200 from {args.url}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
