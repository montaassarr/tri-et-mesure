# Build context: repository root (docker build -f apps/api/Dockerfile .)
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.9.10 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY apps/api/ ./
RUN uv sync --frozen --no-dev

FROM python:3.12-slim
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
COPY --chown=app:app data/gold /data/gold
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health/live')"
CMD ["sh", "-c", "alembic upgrade head && uvicorn tri_mesure.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
