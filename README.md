# AlignAI

> EU AI Act compliance check — describe a feature, get back a structured compliance report grounded in the regulation text.

![Backend CI](https://github.com/jvxoq/alignai/actions/workflows/backend.yml/badge.svg)
![Agent CI](https://github.com/jvxoq/alignai/actions/workflows/agent.yml/badge.svg)
![Frontend CI](https://github.com/jvxoq/alignai/actions/workflows/frontend.yml/badge.svg)

---

## Tech Stack

| Service | Stack |
|---------|-------|
| `frontend/` | React 18 + Vite, deployed to Vercel |
| `backend/` | FastAPI + SQLAlchemy (async) + PostgreSQL, JWT auth, Alembic migrations |
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
