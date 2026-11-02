FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

COPY pyproject.toml uv.lock ./
COPY services/api/pyproject.toml services/api/pyproject.toml
COPY services/agent/pyproject.toml services/agent/pyproject.toml
COPY services/mcp/pyproject.toml services/mcp/pyproject.toml
COPY packages/rag/pyproject.toml packages/rag/pyproject.toml
COPY evals/pyproject.toml evals/pyproject.toml

RUN uv sync --frozen --no-dev --package kb-agent --no-install-workspace

COPY packages/rag packages/rag
COPY services/agent services/agent

RUN uv sync --frozen --no-dev --package kb-agent --no-editable

FROM python:3.12-slim-bookworm

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --home-dir /home/app app \
    && install -d -o app -g app /home/app/.cache

WORKDIR /app

# fastembed downloads models at runtime; keep its cache writable by the runtime user.
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/app/.cache/huggingface \
    FASTEMBED_CACHE_PATH=/home/app/.cache/fastembed

COPY --from=builder /app/.venv /app/.venv

USER app

CMD ["python", "-m", "kb_agent", "start"]
