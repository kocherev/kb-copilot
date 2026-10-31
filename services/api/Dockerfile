FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:${PATH}"

COPY pyproject.toml uv.lock ./
COPY services/api/pyproject.toml services/api/pyproject.toml
COPY services/agent/pyproject.toml services/agent/pyproject.toml
COPY packages/rag packages/rag
COPY evals/pyproject.toml evals/pyproject.toml

RUN uv sync --frozen --no-dev --package kb-api --no-install-project

COPY services/api services/api
COPY demo demo
COPY scripts scripts

RUN uv sync --frozen --no-dev --package kb-api

EXPOSE 8000

CMD ["sh", "-c", "python scripts/wait_for_http.py http://qdrant:6333/readyz --timeout 60 && exec uvicorn kb_api.main:app --host 0.0.0.0 --port 8000"]
