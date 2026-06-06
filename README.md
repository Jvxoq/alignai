# AlignAI

A monorepo containing three independently deployable services for AI-powered feature alignment auditing.

## Architecture

```
alignai/
├── backend/    ← FastAPI service (HTTP API, session management, SSE streaming)
├── agent/      ← LangGraph service (intent routing, retrieval, generation)
└── frontend/   ← React service (UI, SSE consumer)
```

| Concern | Decision | Scope |
| --- | --- | --- |
| Repo organisation | Monorepo | Across all services |
| Code architecture | Onion/layered | Inside `backend/` and `agent/` |
| Frontend architecture | Component-based | Inside `frontend/` |
| Deployment | Independent per service | Render — each service points to its subfolder |

### Data Flow

1. **Frontend** sends `POST /align` with feature text and session ID
2. **Backend** validates session, streams SSE events from the LangGraph agent
3. **Agent** classifies intent, retrieves context from Qdrant, generates alignment report

## Local Development

### Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Python 3.12+ (uv will install if missing)
- Node.js 20+
- PostgreSQL (optional for skeleton — stubs work without DB)
- Qdrant (optional for skeleton)

### Backend

```bash
cd backend
uv sync
cp .env.example .env
uv run uvicorn main:app --reload
```

Health check: `curl http://localhost:8000/health`

### Agent

```bash
cd agent
uv sync
cp .env.example .env
uv run langgraph dev
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

## Testing

```bash
# Backend
cd backend && uv sync --all-groups && uv run pytest

# Agent
cd agent && uv sync --all-groups && uv run pytest

# Frontend
cd frontend && npm run build
```

## Deployment (Render)

Each service deploys independently from its subfolder:

| Service | Root Directory | Dockerfile |
| --- | --- | --- |
| Backend | `backend/` | `backend/Dockerfile` |
| Agent | `agent/` | `agent/Dockerfile` |
| Frontend | `frontend/` | `frontend/Dockerfile` |

Set environment variables per service using the corresponding `.env.example` as reference.

## Environment Variables

See [.env.example](.env.example) for the unified reference, or per-service examples:

- [backend/.env.example](backend/.env.example)
- [agent/.env.example](agent/.env.example)
- [frontend/.env.example](frontend/.env.example)
