#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

pnpm install --frozen-lockfile
pnpm lint
pnpm typecheck
pnpm test

uv sync --frozen --all-packages --group dev
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest

docker compose config --quiet

if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect --source . --redact
else
  echo "gitleaks is not installed. CI still runs it."
fi
