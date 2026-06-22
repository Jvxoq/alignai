FROM python:3.12-slim

RUN adduser --disabled-password --gecos "" appuser

WORKDIR /app

# Install uv as root
RUN pip install uv --no-cache-dir

# Give appuser ownership of workdir so uv sync can create .venv
RUN chown appuser:appuser /app

# Switch to non-root before creating .venv so ownership is correct
USER appuser

# Install dependencies first (layer caching)
COPY --chown=appuser:appuser pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy source (after deps for better caching)
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser main.py alembic.ini ./
COPY --chown=appuser:appuser migrations/ ./migrations/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s \
  CMD [".venv/bin/python", "-c", "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"]

# Run migrations then start server (call venv binaries directly — no `uv run`,
# which would re-sync dev deps into the container at startup)
CMD ["sh", "-c", ".venv/bin/alembic upgrade head && .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000"]
