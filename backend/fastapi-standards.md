# FastAPI Backend Standards

The conventions this backend is built on, and that reviewers hold it to. These
aren't style preferences — most map to a specific production failure they prevent.

Each rule notes whether it's **Non-negotiable** (get it wrong and it hurts in
prod), **Expected** (standard, but applied with judgment), or **Good practice**.

> **The meta-rule:** the mark of a senior backend dev isn't following all of these
> — it's knowing *which to bend and when*. Skip the service layer on a trivial
> endpoint if you like; **never** let a blocking call into an async route. The
> first is cosmetic, the second is an outage.

---

## Architecture & boundaries

### 1. Layered architecture: routes → services → infrastructure *(Expected)*
- **Routes** (`app/api/routes/`) handle HTTP only: parse the request, call a
  service, shape the response. No SQL, no `httpx` calls here.
- **Services** (`app/services/`) hold business logic — `auth_service.py`,
  `session_service.py`, `align_service.py`.
- **Infrastructure** (`app/infrastructure/`) owns I/O — `database.py`, `auth.py`,
  `langgraph_client.py`.

**Why:** you can unit-test business logic without a live HTTP server or DB.

**The judgment call:** layer *because it earns its keep*, not dogmatically. A
service method that only forwards one call to a repo is over-layering — its own
smell. The load-bearing rule is narrower: **no I/O or business logic in the HTTP
layer.**

### 2. Pydantic models at every boundary *(Expected)*
Every request body and response has its own model (`app/models/requests.py`,
`app/models/responses.py`). Never pass raw dicts across a boundary.

**Why:** bad input is rejected with a clean `422` before it reaches your code,
and `/docs` is generated automatically from these models.

### 3. Dependency Injection via `Depends()`, not module-level globals *(Non-negotiable)*
"Current user", "DB session", "settings" are dependency functions
(`app/api/dependencies.py`) injected into route signatures. Never import a live
DB connection at module scope.

**Why:** tests override a dependency with a fake in one line. Globals make that
impossible.

### 4. `main.py` only wires the app together *(Expected)*
`main.py` creates the app, registers middleware / exception handlers / routers,
and defines the `lifespan` startup/shutdown. No business logic. Ours holds the
`lifespan` (logging setup, keep-alive task), CORS, the rate-limit handler, and
`include_router` calls — nothing more. Keep it that way.

---

## Correctness & safety

### 5. Async all the way down *(Non-negotiable — the #1 FastAPI bug)*
If a route is `async def`, **everything it awaits must be async-native**:
- SQLAlchemy async engine + `asyncpg` — not a sync driver
- `httpx.AsyncClient` — not `requests`
- `asyncio.sleep` — not `time.sleep`

**Why:** a single blocking call in an `async` route stalls the entire event loop
— every concurrent request freezes, not just that one. This is a real outage
cause. If you *must* call blocking code, push it to a thread
(`await asyncio.to_thread(...)` / `run_in_executor`).

### 6. Configuration via `pydantic-settings`, never scattered `os.getenv` *(Non-negotiable)*
One `Settings` class in `app/core/config.py`, cached, and **validated** (e.g. a
"secret key must be strong" validator). No `os.getenv` anywhere else in the code.

**Why:** config is validated once at startup, so a missing/weak value fails loudly
on boot instead of silently at 3am.

### 7. Explicit error handling; never leak a stack trace *(Expected)*
Raise `HTTPException(status_code=..., detail=...)` for *expected* failures
(not found, unauthorized, bad request). Register global exception handlers for
*unexpected* ones so clients get a clean error, never a raw traceback. (We already
do this for `RateLimitExceeded`.)

### 8. Migrations are versioned code, never manual SQL *(Non-negotiable)*
Every schema change is an Alembic revision in `migrations/versions/`, reviewed
like any other code. Never hand-run `ALTER TABLE` against prod.

**Why:** hand-run DDL against prod is how you get an irreversible data-loss
incident. Alembic gives you review, history, and a down-path.

### 9. Transactions around multi-step writes *(Good practice)*
Any operation that writes more than one row runs inside a single transaction, so a
mid-failure can't leave half-written state. Design writes to be idempotent where a
client might retry.

---

## Quality gates & tooling

### 10. Types + lint are enforced in CI, not "IDE suggestions" *(Non-negotiable)*
The bar isn't "the tools ran locally once" — it's **the build fails without them.**
This repo's `.github/workflows/backend.yml` runs, on every push and PR touching
`backend/`:

```
uv run ruff check .          # lint
uv run mypy app/             # type check
uv run pytest --cov=app --cov-fail-under=75   # tests + coverage floor
```

`.pre-commit-config.yaml` mirrors the lint step locally so issues are caught
before pushing. Setup: `pip install pre-commit && pre-commit install`.

> **Gap to close:** pre-commit currently runs **ruff only** — `mypy` and `pytest`
> run in CI but *not* locally. So a type error passes your commit and fails CI.
> Either add a local `mypy` hook, or treat CI as the true gate and just know your
> commit isn't the final word.

### 11. Tests separate unit from integration *(Expected)*
- `tests/unit/` — mock out infrastructure, test services in isolation. Fast, cheap.
- `tests/integration/` — hit a real test DB via `httpx.AsyncClient` against the
  actual app. Catches wiring bugs unit tests can't.

Both matter. CI enforces a **75% coverage floor** (`--cov-fail-under=75`).

### 12. Structured logging with context, never `print()` *(Good practice)*
Log through the configured logger (`app/core/logging.py`), not `print`. Aim to
attach request-scoped context (a request ID) so one request is traceable across
services. Logs are for the operator reading them at 3am — write for that reader.

### 13. Secrets never in code or committed env *(Non-negotiable)*
`.env` is gitignored; only `.env.example` (keys, no values) is committed. In
deploy config, real secrets are injected at deploy time (`sync: false` in
`render.yaml`), never checked in. A leaked secret in git history is leaked
forever, even after you delete it.

---

## Performance watch-list

Beyond rule #5 (the big one), the two most common backend performance bugs:

- **N+1 queries** — a loop that issues one query per item instead of one query
  total. Watch for DB calls inside `for` loops; use a join or a batched
  `IN (...)` / `selectinload`.
- **Unbounded results** — always paginate or `LIMIT` list endpoints. "It was fast
  in dev" means "dev had 10 rows."

---

## Quick self-check before opening a PR

- [ ] No SQL / `httpx` calls inside a route function
- [ ] No blocking call inside any `async def` (no `requests`, `time.sleep`, sync DB)
- [ ] New request/response shapes have Pydantic models
- [ ] New config reads go through `Settings`, not `os.getenv`
- [ ] Schema change has an Alembic migration
- [ ] `ruff check .`, `mypy app/`, and `pytest` all pass locally
- [ ] No secret added to a committed file
