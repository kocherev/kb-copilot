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

RUN uv sync --frozen --no-dev --package kb-agent --no-install-project

COPY services/agent services/agent

RUN uv sync --frozen --no-dev --package kb-agent

CMD ["python", "-m", "kb_agent", "start"]
