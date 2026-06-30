<system_directive>
You are operating within the AlignAI monorepo. The following architectural rules, code styles, and constraints are ABSOLUTE. You must apply them to every single file modification, generation, or refactor, no matter how small. 
</system_directive>

<project_overview>
Three independent services in a monorepo — no shared Python imports, no single deploy unit.

| Service | Stack | Onion layers: outer → inner |
|---------|-------|------------------------------|
| `backend/` | FastAPI + SQLAlchemy async | `api/` → `services/` → `infrastructure/` + `models/` → `core/` |
| `agent/` | LangGraph | `graph/` → `nodes/` → `infrastructure/` + `prompts/` → `core/` |
| `frontend/` | React 18 + Vite 6 (`.jsx`) | `components/` → `hooks/` + `services/` → `styles/` |
</project_overview>

<code_style>
- **Types**: Type hints on every function signature.
- **Schemas**: Pydantic v2 `BaseModel` in `backend/app/models/`; `TypedDict` with `Annotated` merge in `agent/app/graph/state.py`.
- **Config**: `pydantic-settings.BaseSettings` + `@lru_cache` + `get_settings()` in `core/config.py` — never hardcode env vars.
- **Logging**: `from pythonjsonlogger.json import JsonFormatter` in `core/logging.py` — never `print()`.
- **Async**: `async def` in all FastAPI routes/services and LangGraph nodes.
- **Python deps**: `uv` + per-service `pyproject.toml` / `uv.lock` — never `pip install` or `requirements.txt`.
- **Ingestion dep**: `pymupdf` is the only PDF parser used in `agent/ingest.py`. It is declared in `agent/pyproject.toml`. No other PDF libraries (`pypdf`, `pdfplumber`, `pdfminer`) should be added.
- **Frontend deps**: `npm` in `frontend/package.json` only.
</code_style>

<architecture_rules>
- **Outer layers depend inward; inner layers never depend outward.**
  - Routes (`api/`) call services, never infrastructure or DB directly.
  - Nodes call infrastructure, never Qdrant/embeddings directly.
  - `core/` is import-only by everything; it never imports from `api/`, `services/`, `nodes/`, or `graph/`.
- **No cross-service imports.** `backend/` never imports from `agent/` or vice versa. `backend/infrastructure/langgraph_client.py` talks to the agent via HTTP (langgraph-sdk), not Python imports.
- **Business logic stays in `services/` (backend) or `nodes/` (agent)** — never in routes or graph wiring.
- **All external I/O** (DB, Qdrant, embeddings, LangGraph SDK) goes through `infrastructure/`.
</architecture_rules>

<file_placement>
| What | Where |
|------|-------|
| New route | `backend/app/api/routes/<name>.py` |
| New dependency | `backend/app/api/dependencies.py` |
| New service | `backend/app/services/<name>_service.py` |
| New infrastructure | `backend/app/infrastructure/<name>.py` or `agent/app/infrastructure/<name>.py` |
| New model | `backend/app/models/<name>.py` |
| New node | `agent/app/nodes/<name>_node.py` |
| New prompt | `agent/app/prompts/<name>_prompt.py` |
| New graph/edge | `agent/app/graph/edges.py` or `agent/app/graph/graph.py` |
| New component | `frontend/src/components/<Section>/<PascalName>.jsx` |
| New hook | `frontend/src/hooks/use<hookName>.js` |
| New API client | `frontend/src/services/<name>.js` |
| Config/env var | Only in `core/config.py` (never hardcoded in routes/services/nodes) |
</file_placement>

<ci_deployability>
- **Do not edit CI workflows** unless the task explicitly requires it and you verify the path filter matches the changed service.
- Backend CI: `.github/workflows/backend.yml` — `uv sync --all-groups` + `uv run pytest`
- Agent CI: `.github/workflows/agent.yml` — `uv sync --all-groups` + `uv run pytest`
- Frontend CI: `.github/workflows/frontend.yml` — `npm install` + `npm run build`
- Adding a Python dependency: update the correct `pyproject.toml` (backend/ or agent/) and run `uv lock` in that directory.
</ci_deployability>

<critical_constraints>
NEVER DO THE FOLLOWING:
- ❌ Hardcode secrets, URLs, or env vars outside `core/config.py`.
- ❌ Bare `except Exception:` without logging via `logger.exception()`.
- ❌ Business logic in route handlers or graph wiring.
- ❌ Direct DB/Qdrant/embedding calls outside `infrastructure/`.
- ❌ Import across service boundaries (`backend/` ←→ `agent/`).
- ❌ Touch CI/Dockerfile for a service not relevant to the task.
- ❌ Add markdown/docs files (including README changes) unless explicitly asked.
- ❌ Commit `.env`, `.venv`, `node_modules`, `__pycache__/`.
- ❌ Add new dependencies without updating `pyproject.toml` + running `uv lock`.
- ❌ Drive-by refactors, formatting changes, or renaming existing symbols.
</critical_constraints>

<git_rules>
- Commit only when explicitly asked.
- Before committing: check `git status`, `git diff`, stage only intended files.
- Concise commit messages matching repo style (imperative, lowercase).
</git_rules>
