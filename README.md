# AlignAI

> EU AI Act compliance check — describe a feature, get back a structured compliance report grounded in the regulation text.

[![Backend CI](https://github.com/jvxoq/alignai/actions/workflows/backend.yml/badge.svg)](https://github.com/jvxoq/alignai/actions/workflows/backend.yml)
[![Agent CI](https://github.com/jvxoq/alignai/actions/workflows/agent.yml/badge.svg)](https://github.com/jvxoq/alignai/actions/workflows/agent.yml)
[![Frontend CI](https://github.com/jvxoq/alignai/actions/workflows/frontend.yml/badge.svg)](https://github.com/jvxoq/alignai/actions/workflows/frontend.yml)

**[Live demo](https://alignai-eight.vercel.app)** · **[Docs](PROJECT_DOC.md)** · **[Backend](backend/)** · **[Agent](agent/)**

---

## Why this shows backend + agent skills

Not a notebook wrapper. Three deployed services with a real backend in the middle.

- **Backend (FastAPI async)** — `FastAPI + SQLAlchemy (async) + PostgreSQL + Alembic + JWT + SSE`. Owns users/sessions, proxies to the agent over HTTP via `langgraph-sdk` (no shared imports), streams back as SSE. `Alembic` owns the schema everywhere — no `create_all` anywhere. See `PROJECT_DOC.md` for the full flow.
- **Agent (LangGraph)** — official `langgraph-api` server image. Graph: `intent → retrieve (Gemini + Qdrant) → relevance check → generate (Groq) → fallback`, with up to 3 rewrite loops. Retrieval filtered by article/chapter metadata, falls back gracefully when nothing relevant is found (no hallucinating).
- **Infra** — `Qdrant Cloud` (vectors), `Redis` (queue), `Groq` (LLM), `Gemini` (embeddings), `Neon` Postgres, `Docker Compose` for local parity, separate CI per service (75% backend, 55% agent coverage gates).

```
frontend (Vercel) ──HTTPS──> backend (Render, FastAPI) ──HTTP (langgraph-sdk)──> agent (Render, langgraph-api)
        ◀── SSE stream ──────        ◀── SSE stream (proxied) ──────────────────
                                      │
                                      ▼
                               Postgres (Neon)  ←── LangGraph checkpoints
                                      │
                               Qdrant + Redis + Groq/Gemini
```

See [`PROJECT_DOC.md`](PROJECT_DOC.md) for architecture, data flow, and operational concerns.

---

## Tech Stack

| Service | Stack |
|---------|-------|
| `frontend/` | React 18 + Vite, deployed to Vercel |
| `backend/` | FastAPI + SQLAlchemy (async) + PostgreSQL, JWT auth, Alembic migrations, SSE streaming |
| `agent/` | LangGraph (official `langgraph-api` server image) + Groq (LLM) + Gemini (embeddings) + Qdrant (vector search) + Redis (queue) |

---

## Running Locally

### Backend + agent at once (Docker Compose)

```bash
cp .env.example .env   # fill in GROQ_API_KEY, GEMINI_API_KEY, QDRANT_URL, QDRANT_API_KEY, LANGSMITH_API_KEY
make dev                # hot-reload dev stack
make prod                # production-parity stack (lean images, no hot reload)
```

Both serve: backend on `http://localhost:8000`, agent on `http://localhost:8123`. The
frontend deploys to Vercel and isn't in the Docker stack — run it separately (below).

### Each service on its own

**Frontend**
```bash
cd frontend
cp .env.example .env
npm install
npm run dev              # http://localhost:5173
```

**Backend**
```bash
cd backend
cp .env.example .env     # set SECRET_KEY, POSTGRES_URL
uv sync
uv run alembic upgrade head
uv run uvicorn main:app --reload   # http://localhost:8000
```

**Agent**
```bash
cd agent
cp .env.example .env     # set GROQ_API_KEY, GEMINI_API_KEY, QDRANT_URL, QDRANT_API_KEY
uv sync
uv run langgraph dev     # http://localhost:8123
```

---

## License

[MIT](LICENSE)
