#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

pnpm install --frozen-lockfile
pnpm lint
pnpm typecheck
pnpm test
# Prerendering runs only in a production build, so lint and tests cannot catch
# a page that fails it. Better Auth logs an error for each page without a
# secret; this one exists only for the build and is never served.
BETTER_AUTH_SECRET="${BETTER_AUTH_SECRET:-check-sh-build-only-placeholder-secret}" pnpm build

uv sync --frozen --all-packages --group dev
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
uv run python -m kb_evals

docker compose config --quiet
docker compose --profile livekit config --quiet

if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect --source . --redact
else
  echo "gitleaks is not installed. CI still runs it."
fi
