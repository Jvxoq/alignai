# AlignAI

> AI-powered EU AI Act compliance auditing platform — developers describe a feature and receive a structured alignment report grounded in regulatory documents.

![Backend CI](https://github.com/Jvxoq/alignai/actions/workflows/backend.yml/badge.svg)
![Agent CI](https://github.com/Jvxoq/alignai/actions/workflows/agent.yml/badge.svg)
![Frontend CI](https://github.com/Jvxoq/alignai/actions/workflows/frontend.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)

**What this project demonstrates:** async **FastAPI** with a layered (router → service → repository) architecture, a **LangGraph** RAG agent (intent classification → semantic retrieval → report generation), **JWT auth** with refresh-token rotation, **Server-Sent Events** streaming to the browser, and **per-service CI** across three independently deployable apps (backend, agent, frontend).

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Tech Stack](#tech-stack)
4. [Repository Layout](#repository-layout)
5. [Prerequisites](#prerequisites)
6. [Getting Started](#getting-started)
7. [Environment Variables](#environment-variables)
8. [Running the App](#running-the-app)
9. [Running Tests](#running-tests)
10. [API Reference](#api-reference)
11. [Key Workflows](#key-workflows)
12. [Deployment](#deployment)
13. [Contributing](#contributing)
14. [Troubleshooting](#troubleshooting)
15. [License](#license)

---

## Overview

AlignAI is a compliance-as-a-service tool aimed at AI developers and product teams who need to assess their systems against the EU AI Act. A user describes their feature or AI system in plain language; AlignAI classifies the intent, retrieves the most relevant regulatory passages from a vector database of EU AI Act documents, and streams a structured alignment report back to the browser in real time.

The platform is designed for developer portfolios and early-stage compliance teams. It is currently in **beta** — all three services (frontend, backend, agent) are independently deployable on Render's free tier, making it cheap to run at low traffic.

The core differentiator is a LangGraph-powered agent that handles the full retrieval-augmented generation (RAG) pipeline: intent classification → semantic retrieval → report generation → streaming delivery. The backend acts as a thin orchestration layer, keeping auth and session state separate from AI logic.

---

## Architecture

AlignAI is a **monorepo** containing three independently deployable services that communicate over HTTP:

```
Browser ──HTTP──▶ React SPA (port 80 / 5173)
                        │
                  REST + SSE stream
                        │
                  FastAPI Backend (port 8000)
                  ├── JWT auth & rate limiting
                  ├── Session / user management (PostgreSQL)
                  └── LangGraph SDK client
                               │
                         HTTP (LangGraph API)
                               │
                  LangGraph Agent (port 8123)
                  ├── Intent node  ──▶ Groq LLM (classify)
                  ├── Retriever node ──▶ Gemini (embed) + Qdrant Cloud (search)
                  ├── Generator node ──▶ Groq LLM (stream report)
                  └── Fallback node  (no relevant docs after 3 retries)
                               │
                         PostgreSQL (checkpoints)
                         Qdrant Cloud (vector store)
```

**End-to-end data flow for an alignment request:**

1. User submits a feature description in the frontend.
2. Frontend sends `POST /align` with a `session_id` and `message` — the backend validates the JWT and looks up the session.
3. Backend opens an SSE stream from the LangGraph agent via the LangGraph SDK.
4. The agent runs the graph: **intent node** classifies the input (compliance query vs. general chat); if it is a compliance query, the **retriever node** embeds the text via Gemini and searches Qdrant for the top-K relevant document chunks; the **generator node** streams a regulation-grounded report token-by-token back through the backend to the browser.
5. If no relevant documents are found after three retries, the **fallback node** sends a graceful response.
6. The frontend consumes the SSE stream and renders the report incrementally using `react-markdown`.

---

## Tech Stack

| Layer | Technology | Version / Notes |
|-------|-----------|-----------------|
| Frontend | React | 18.3 |
| Frontend | Vite | 6.x — dev server and production bundler |
| Frontend | React Router | v6 |
| Frontend | react-markdown | 9.x — renders streamed report |
| Frontend (prod) | Nginx | Serves static build inside Docker |
| Backend | Python | 3.12+ |
| Backend | FastAPI | 0.115+ |
| Backend | SQLAlchemy (async) | 2.x + asyncpg driver |
| Backend | Alembic | DB migrations |
| Backend | python-jose | JWT access + refresh tokens |
| Backend | passlib / bcrypt | Password hashing |
| Backend | slowapi | Rate limiting |
| Backend | tenacity | Retry with exponential backoff |
| Agent | LangGraph | 0.2+ — state-machine agent orchestration |
| Agent | LangGraph SDK | Backend-to-agent HTTP client |
| Agent | LangChain-Groq | Groq LLM (intent classification, generation) |
| Agent | google-genai | Gemini (text embeddings) |
| Agent | qdrant-client | Vector similarity search |
| Agent | pymupdf / pymupdf4llm | PDF ingestion for document corpus |
| Database | PostgreSQL 16 | User/session storage + LangGraph checkpoints |
| Vector DB | Qdrant Cloud | EU AI Act document embeddings (external SaaS) |
| Package manager | uv | Python — backend and agent |
| Package manager | npm | Frontend |
| Containerisation | Docker + Compose | Full local stack |
| CI | GitHub Actions | Per-service workflows |
| Hosting | Render | Docker web services (free tier) |

---

## Repository Layout

```
alignai/                          # Repo root
├── backend/                      # FastAPI service
│   ├── app/
│   │   ├── api/routes/           # Route handlers (auth, sessions, align, users)
│   │   ├── core/                 # Config, security, logging
│   │   ├── infrastructure/       # DB session factory, repository layer
│   │   ├── models/               # SQLAlchemy ORM models
│   │   └── services/             # Business logic (auth, sessions, align streaming)
│   ├── migrations/               # Alembic migration scripts
│   ├── tests/
│   │   ├── unit/                 # Service-level unit tests (mocked DB)
│   │   └── integration/          # Endpoint tests via FastAPI TestClient
│   ├── main.py                   # App entry point — mounts all routers
│   ├── Dockerfile
│   └── pyproject.toml
├── agent/                        # LangGraph agent service
│   ├── app/
│   │   ├── core/                 # Config, logging, utilities
│   │   ├── graph/                # LangGraph graph definition, state, edges
│   │   ├── nodes/                # Agent nodes (intent, retriever, generator, fallback, rewrite)
│   │   ├── prompts/              # Prompt templates per node
│   │   ├── infrastructure/       # LLM client, Qdrant client, embedding client, ingest pipeline
│   │   └── models/               # Pydantic models (IntentType, etc.)
│   ├── tests/
│   │   ├── unit/                 # Node-level tests (mocked LLM + Qdrant)
│   │   └── integration/          # Live Qdrant + embedding tests
│   ├── ingest.py                 # CLI script: load PDFs into Qdrant
│   ├── retrieve.py               # CLI script: test a retrieval query
│   ├── langgraph.json            # LangGraph server config
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/                     # React SPA
│   ├── src/
│   │   ├── components/           # Reusable UI (StatusIndicator, CharacterCounter, etc.)
│   │   ├── context/              # AuthContext — user session state
│   │   ├── hooks/                # useStream — SSE consumer hook
│   │   ├── pages/                # Route-level components (Login, Dashboard, Audit, etc.)
│   │   ├── services/             # API call wrappers (authService, sessionService, etc.)
│   │   ├── styles/               # Global CSS variables and resets
│   │   └── test/                 # Vitest setup and shared test utils
│   ├── nginx.conf                # Nginx config for production container
│   ├── Dockerfile
│   ├── package.json
│   └── vite.config.js
├── .github/workflows/            # CI — backend.yml, agent.yml, frontend.yml
├── docker-compose.yml            # Full local stack (postgres + backend + agent + frontend)
├── render.yaml                   # Render Blueprint — backend + agent deploy config
├── healthcheck.py                # Simple HTTP healthcheck script
├── test-docker-setup.sh          # Smoke test for the Docker stack
└── .env.example                  # Root env file used by docker-compose variable substitution
```

**Top-level directories:**

- `backend/` — FastAPI service that owns auth, session management, and SSE proxying to the agent.
- `agent/` — LangGraph service that owns all AI logic: intent routing, RAG retrieval, and report generation.
- `frontend/` — React SPA that renders the audit UI and consumes the SSE stream.
- `.github/workflows/` — Three independent CI pipelines, one per service.

---

## Prerequisites

| Tool | Minimum version | Install |
|------|----------------|---------|
| Python | 3.12 | [python.org](https://python.org) or via uv |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js | 20 | [nodejs.org](https://nodejs.org) |
| npm | 10 | Bundled with Node.js 20 |
| Docker + Docker Compose | 24 / v2 | [docs.docker.com](https://docs.docker.com/get-docker/) |

**External accounts required:**

| Service | Purpose | Notes |
|---------|---------|-------|
| [Groq](https://console.groq.com) | LLM inference (intent + generation) | Free tier available; `GROQ_API_KEY` |
| [Google AI Studio](https://aistudio.google.com) | Text embeddings (Gemini) | Free tier available; `GEMINI_API_KEY` |
| [Qdrant Cloud](https://cloud.qdrant.io) | Vector database | Free cluster available; `QDRANT_URL` + `QDRANT_API_KEY` |
| LangSmith *(optional)* | Agent trace observability | `LANGSMITH_API_KEY` |

---

## Getting Started

### Option A — Docker Compose (recommended, runs the full stack)

```bash
# 1. Clone the repo
git clone https://github.com/Jvxoq/alignai.git
cd alignai

# 2. Create the root .env file used by docker-compose variable substitution
cp .env.example .env

# 3. Fill in the four required API keys in .env
#    GROQ_API_KEY=...
#    GEMINI_API_KEY=...
#    QDRANT_URL=...        (e.g. https://xxxx.cloud.qdrant.io:6333)
#    QDRANT_API_KEY=...

# 4. (One-time) Ingest documents into Qdrant
#    Skip if your Qdrant collection is already populated.
cd agent
cp .env.example .env   # fill in the same keys
uv sync
uv run python ingest.py
cd ..

# 5. Build and start all services
docker compose up --build

# 6. Verify each service is healthy
curl http://localhost:8000/health   # {"status":"ok"}
curl http://localhost:8123/ok       # {"ok":true}
# Frontend: http://localhost
```

### Option B — Manual (run each service on the host)

```bash
# ── Backend ──────────────────────────────────────────────────────────────────
cd backend
cp .env.example .env
# Edit .env: set SECRET_KEY to any random 32+ character string.
# POSTGRES_URL defaults to localhost:5432 — start a local Postgres first.
uv sync
uv run alembic upgrade head         # apply DB migrations
uv run uvicorn main:app --reload    # http://localhost:8000

# ── Agent ─────────────────────────────────────────────────────────────────────
cd ../agent
cp .env.example .env
# Edit .env: set GROQ_API_KEY, GEMINI_API_KEY, QDRANT_URL, QDRANT_API_KEY.
uv sync
uv run langgraph dev                # http://localhost:8123

# ── Frontend ──────────────────────────────────────────────────────────────────
cd ../frontend
cp .env.example .env
# VITE_API_BASE_URL=http://localhost:8000 (default is correct for local dev)
npm install
npm run dev                         # http://localhost:5173
```

---

## Environment Variables

### Root `.env` — used by `docker-compose` only

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | **Yes** | Groq API key for LLM inference (intent + generation nodes) |
| `GEMINI_API_KEY` | **Yes** | Google Gemini API key for text embeddings |
| `QDRANT_URL` | **Yes** | Qdrant Cloud cluster URL (e.g. `https://xxxx.cloud.qdrant.io:6333`) |
| `QDRANT_API_KEY` | **Yes** | Qdrant Cloud API key |

### `backend/.env` — host-only (not used inside Docker)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POSTGRES_URL` | **Yes** | `postgresql+asyncpg://postgres:password@localhost:5432/alignai` | Async SQLAlchemy connection string |
| `LANGGRAPH_SERVER_URL` | **Yes** | `http://localhost:8123` | URL of the running LangGraph agent |
| `SECRET_KEY` | **Yes** | *(none)* | Random 32+ char string for JWT signing — generate with `openssl rand -hex 32` |
| `CORS_ORIGINS` | No | `["http://localhost:5173"]` | JSON array of allowed CORS origins |
| `ENVIRONMENT` | No | `development` | `development` or `production` |

### `agent/.env` — host-only (not used inside Docker)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `QDRANT_URL` | **Yes** | *(none)* | Qdrant Cloud cluster URL |
| `QDRANT_API_KEY` | **Yes** | *(none)* | Qdrant Cloud API key |
| `QDRANT_COLLECTION_NAME` | No | `alignai_docs` | Name of the Qdrant collection |
| `GROQ_API_KEY` | **Yes** | *(none)* | Groq API key |
| `GEMINI_API_KEY` | **Yes** | *(none)* | Google Gemini API key |
| `ENVIRONMENT` | No | `development` | `development` or `production` |
| `INTENT_LLM_MODEL` | No | `llama-3.3-70b-versatile` | Groq model for intent classification |
| `GENERATOR_LLM_MODEL` | No | `llama-3.3-70b-versatile` | Groq model for report generation |

### `frontend/.env` — host-only (not used inside Docker)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VITE_API_BASE_URL` | No | `http://localhost:8000` | Backend base URL — inlined into the JS bundle at build time; **never put secrets here** |

---

## Running the App

### Development (Docker Compose)

```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend (Nginx) | http://localhost |
| Backend API + Swagger | http://localhost:8000/docs |
| Agent health | http://localhost:8123/ok |
| PostgreSQL | localhost:5432 |

### Development (host)

```bash
# Terminal 1 — backend
cd backend && uv run uvicorn main:app --reload

# Terminal 2 — agent
cd agent && uv run langgraph dev

# Terminal 3 — frontend
cd frontend && npm run dev
```

Frontend dev server: http://localhost:5173 (Vite HMR, proxies nothing — CORS is handled by the backend).

### Production build (frontend only)

```bash
cd frontend
VITE_API_BASE_URL=https://your-backend.onrender.com npm run build
# Output in frontend/dist/ — served by Nginx in the Docker image
```

---

## Running Tests

### Backend

```bash
cd backend
uv sync --all-groups

uv run pytest -v                    # all tests
uv run pytest --cov=app tests/      # with coverage report
uv run ruff check .                 # linting
uv run mypy app/                    # type checking
```

Tests live in `backend/tests/`:
- `unit/` — service-level tests with mocked DB and mocked LangGraph client
- `integration/` — endpoint tests via FastAPI `TestClient` (in-memory, no real DB required)

### Agent

```bash
cd agent
uv sync --all-groups

uv run pytest -v                    # all tests
```

Tests live in `agent/tests/`:
- `unit/` — node-level tests with mocked LLM and Qdrant clients
- `integration/` — live Qdrant + Gemini embedding tests (require real API keys in `agent/.env`)

> **Note:** integration tests hit live external services. They are excluded from CI by default — only unit tests run in GitHub Actions.

### Frontend

```bash
cd frontend

npm test              # watch mode (Vitest)
npm test -- --run     # CI mode (single pass)
npm run test:ui       # interactive Vitest UI in browser
npm run lint          # ESLint
```

Tests live in `frontend/src/` co-located with their components, plus shared setup in `frontend/src/test/`. Coverage includes: `useStream` SSE parsing hook, `StatusIndicator`, `CharacterCounter`, `AuditButton`.

---

## API Reference

**Base URL (local):** `http://localhost:8000`

**Authentication:** Bearer token (JWT). Obtain a token via `POST /auth/login`. Pass it in all subsequent requests:
```
Authorization: Bearer <access_token>
```

**Interactive docs:** http://localhost:8000/docs (Swagger UI) · http://localhost:8000/redoc

### Core endpoints

| Method | Path | Auth? | Description |
|--------|------|-------|-------------|
| `GET` | `/health` | No | Liveness check — returns `{"status":"ok"}` |
| `POST` | `/auth/signup` | No | Create a new user account |
| `POST` | `/auth/login` | No | Authenticate and receive `access_token` + `refresh_token` |
| `POST` | `/auth/refresh` | No | Exchange a refresh token for a new access token |
| `GET` | `/auth/me` | **Yes** | Return the authenticated user's profile |
| `POST` | `/sessions` | **Yes** | Create a new audit session |
| `GET` | `/sessions` | **Yes** | List sessions for the authenticated user (paginated) |
| `GET` | `/sessions/{id}/messages` | **Yes** | Return message history for a session |
| `PATCH` | `/sessions/{id}` | **Yes** | Rename a session |
| `DELETE` | `/sessions/{id}` | **Yes** | Delete a session |
| `DELETE` | `/users/me` | **Yes** | Delete the authenticated user's account |
| `POST` | `/align` | **Yes** | Submit a compliance query — returns an **SSE stream** of token events |

### SSE stream format (`POST /align`)

The response is `Content-Type: text/event-stream`. Each event is a JSON object:

```
data: {"type": "token", "content": "Based on Article 13..."}
data: {"type": "done"}
data: {"type": "error", "message": "..."}
```

**Rate limits:** Auth endpoints (`/auth/login`, `/auth/signup`) are rate-limited per IP. The `/align` endpoint is rate-limited per user.

---

## Key Workflows

### 1. Adding a new backend API endpoint

1. Create (or add to) a route file in `backend/app/api/routes/<resource>.py`.
2. Mount it in `backend/main.py` via `app.include_router(...)`.
3. Write the business logic in `backend/app/services/<resource>_service.py`.
4. Add or update Pydantic request/response models inline or in a shared schemas file.
5. Add a unit test in `backend/tests/unit/` and an integration test in `backend/tests/integration/`.
6. Run `uv run ruff check . && uv run mypy app/ && uv run pytest` before opening a PR.

### 2. Adding a new agent node

1. Create `agent/app/nodes/<name>_node.py` with a function `async def <name>_node(state: AgentState) -> dict`.
2. Register it in `agent/app/graph/graph.py` with `graph.add_node(...)`.
3. Wire edges in `agent/app/graph/edges.py`.
4. Add a prompt template in `agent/app/prompts/<name>_prompt.py` if the node calls an LLM.
5. Write unit tests in `agent/tests/unit/test_<name>_node.py` with mocked LLM responses.
6. Run `uv run pytest` and verify the graph compiles by running `uv run langgraph dev` locally.

### 3. Ingesting new regulatory documents

EU AI Act documents (PDFs) are pre-processed and stored in Qdrant. To add new documents:

```bash
# Place PDFs in agent/app/infrastructure/docs/ (or update the path in ingest.py)
cd agent
uv run python ingest.py
```

`ingest.py` extracts text via `pymupdf4llm`, chunks it, embeds each chunk with Gemini, and upserts into the `alignai_docs` Qdrant collection.

### 4. Running a local retrieval smoke test

```bash
cd agent
uv run python retrieve.py "Does my facial recognition system fall under the prohibited AI list?"
```

Prints the top-K retrieved chunks and their similarity scores — useful for tuning `SIMILARITY_THRESHOLD` and `RETRIEVAL_TOP_K`.

---

## Deployment

AlignAI deploys to **Render** using the included `render.yaml` Blueprint. The frontend deploys as a Render Static Site (or any CDN) separately.

### Steps

1. Push `render.yaml` to the default branch of your GitHub repo.
2. Render dashboard → **New** → **Blueprint** → select your repo.
3. Before clicking **Deploy**, set these environment variables manually in the Render dashboard (they are marked `sync: false` in the Blueprint — Render will prompt you):

   **alignai-backend:**
   | Variable | Value |
   |----------|-------|
   | `POSTGRES_URL` | Internal DB URL from Render's `alignai-db` page — change scheme to `postgresql+asyncpg://` |
   | `CORS_ORIGINS` | `["https://your-frontend-domain.com"]` |

   **alignai-agent:**
   | Variable | Value |
   |----------|-------|
   | `POSTGRES_URL` | Internal DB URL (leave scheme as `postgresql://`) |
   | `QDRANT_URL` | Your Qdrant Cloud cluster URL |
   | `QDRANT_API_KEY` | Your Qdrant API key |
   | `GROQ_API_KEY` | Your Groq API key |
   | `GEMINI_API_KEY` | Your Gemini API key |

4. After the first successful deploy, **pin `SECRET_KEY`**: copy the auto-generated value from the backend service's env vars and paste it back as a fixed value. This prevents JWT invalidation on future deploys.

5. Run DB migrations after the first backend deploy:
   ```bash
   # From your local machine, pointing at the production DB
   POSTGRES_URL=<production-url> uv run alembic upgrade head
   ```
   Or add a `startCommand` override in `render.yaml` to run migrations before starting the server.

6. Health checks: Render monitors `/health` (backend) and `/ok` (agent) automatically.

### Service configuration summary

| Service | Render type | Dockerfile | Health path |
|---------|------------|------------|-------------|
| alignai-backend | Web Service (Docker) | `backend/Dockerfile` | `/health` |
| alignai-agent | Web Service (Docker) | `agent/Dockerfile` | `/ok` |
| alignai-frontend | Static Site or own CDN | `frontend/Dockerfile` (Nginx) | N/A |
| alignai-db | PostgreSQL (managed) | N/A | N/A |

---

## Contributing

### Branch naming

```
feat/<short-description>
fix/<short-description>
chore/<short-description>
```

### PR checklist

- [ ] Tests pass locally for the affected service (`uv run pytest` or `npm test -- --run`)
- [ ] Backend: linting and type checking pass (`uv run ruff check . && uv run mypy app/`)
- [ ] Frontend: ESLint passes (`npm run lint`)
- [ ] New behaviour is covered by tests
- [ ] Environment variable additions are reflected in the relevant `.env.example`
- [ ] `render.yaml` is updated if new environment variables are required in production

### Commit style

Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`). Keep the subject line under 72 characters.

### Code review

Open a PR against `main`. CI must be green before merging. All three service pipelines only run when files in their respective directories change, so a backend-only PR will not re-run the frontend workflow.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `POST /auth/login` returns 429 | Rate limiter triggered (too many attempts) | Wait 60 seconds, then retry |
| Agent health check fails at startup | Qdrant/LLM env vars missing or wrong | Check `QDRANT_URL`, `GROQ_API_KEY`, `GEMINI_API_KEY` in `.env` or docker-compose |
| `docker compose up` fails — backend waits forever for agent | Agent is crashing on startup due to missing keys | Check agent container logs: `docker compose logs agent` |
| Frontend shows blank page after Docker build | `VITE_API_BASE_URL` was not set at build time | Rebuild with the correct ARG: `docker compose up --build` after editing `.env` |
| `alembic upgrade head` — "can't locate revision" | Migration version table is out of sync | Run `alembic history` to inspect state; restore from a clean DB if needed |
| SSE stream cuts off after a few tokens | `LANGGRAPH_READ_TIMEOUT` too short | Increase to 120+ seconds in backend env |
| `uv sync` fails — Python version mismatch | System Python is older than 3.12 | Install Python 3.12 via uv: `uv python install 3.12` |
| `npm install` fails on Node < 20 | Vite 6 requires Node 20+ | Upgrade Node: `nvm install 20 && nvm use 20` |
| Qdrant search returns no results | Collection not ingested or wrong collection name | Run `python ingest.py` and verify `QDRANT_COLLECTION_NAME` matches |

---

## License

Released under the [MIT License](LICENSE).
