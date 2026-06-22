FROM python:3.12-slim

RUN adduser --disabled-password --gecos "" appuser

WORKDIR /app

RUN pip install uv --no-cache-dir

RUN chown appuser:appuser /app

USER appuser

COPY --chown=appuser:appuser pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser langgraph.json ./

EXPOSE 8123

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s \
  CMD [".venv/bin/python", "-c", "import httpx; httpx.get('http://localhost:8123/ok').raise_for_status()"]

# langgraph dev serves the API server (NOT langgraph up, which orchestrates Docker from the host)
# Call the venv binary directly — `uv run` would re-sync dev deps at startup.
CMD [".venv/bin/langgraph", "dev", "--host", "0.0.0.0", "--port", "8123"]
