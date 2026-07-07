# Production LangGraph API server.
#
# Built on the official `langchain/langgraph-api` image, which serves the full
# LangGraph Server REST API (assistants / threads / runs / streaming) that the
# backend talks to via `langgraph_sdk`. Unlike `langgraph dev`, this image:
#   - persists checkpoints/threads in Postgres (POSTGRES_URI)
#   - runs a real queue + worker backed by Redis (REDIS_URI)
#   - has no file-watcher / browser-opener / in-memory checkpointer
#
# Pinned to the 3.12 base to match `requires-python = ">=3.12"` in pyproject.toml.
# Regenerate the scaffold with: `langgraph dockerfile <path>` (then re-pin the tag).
FROM langchain/langgraph-api:3.12

# -- Install the local agent package (the graph + its runtime deps) --
ADD . /deps/agent
RUN for dep in /deps/*; do \
        if [ -d "$dep" ]; then \
            echo "Installing $dep"; \
            (cd "$dep" && PYTHONDONTWRITEBYTECODE=1 uv pip install --system --no-cache-dir -c /api/constraints.txt -e .); \
        fi; \
    done

# Tell the server which graph(s) to serve. "align_agent" is the assistant_id the
# backend calls (see backend align_service.py / session_service.py).
ENV LANGSERVE_GRAPHS='{"align_agent": "/deps/agent/app/graph/graph.py:graph"}'

# -- Ensure user deps didn't inadvertently overwrite langgraph-api --
RUN mkdir -p /api/langgraph_api /api/langgraph_runtime /api/langgraph_license && \
    touch /api/langgraph_api/__init__.py /api/langgraph_runtime/__init__.py /api/langgraph_license/__init__.py
RUN PYTHONDONTWRITEBYTECODE=1 uv pip install --system --no-cache-dir --no-deps -e /api

# -- Drop build tooling from the final image --
RUN pip uninstall -y pip setuptools wheel; \
    rm -rf /usr/local/lib/python*/site-packages/pip* /usr/local/lib/python*/site-packages/setuptools* /usr/local/lib/python*/site-packages/wheel* && find /usr/local/bin -name "pip*" -delete || true; \
    rm -rf /usr/lib/python*/site-packages/pip* /usr/lib/python*/site-packages/setuptools* /usr/lib/python*/site-packages/wheel* && find /usr/bin -name "pip*" -delete || true; \
    uv pip uninstall --system pip setuptools wheel && rm /usr/bin/uv /usr/bin/uvx

WORKDIR /deps/agent
