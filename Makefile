# AlignAI — local Docker workflows.
#
#   make dev    → development stack (hot-reload, dev deps)   http://localhost
#   make prod   → production-parity stack (lean images)      http://localhost
#   make test   → run all test suites inside the dev containers
#   make down   → stop and remove containers
#
# `dev` uses docker-compose.yml + docker-compose.override.yml (auto-merged).
# `prod` uses ONLY docker-compose.yml, so the override is never applied.

# Explicitly naming the base file makes `prod` skip the auto-loaded dev override.
PROD := docker compose -f docker-compose.yml

.PHONY: dev dev-d prod prod-d down clean logs ps \
        test test-backend test-agent test-frontend

## Development (default) — foreground, with build
dev:
	docker compose up --build

## Development, detached
dev-d:
	docker compose up --build -d

## Production parity — foreground, with build
prod:
	$(PROD) up --build

## Production parity, detached
prod-d:
	$(PROD) up --build -d

## Stop and remove containers (keeps volumes)
down:
	docker compose down

## Stop and remove containers AND named volumes (wipes the local DB)
clean:
	docker compose down -v

## Tail logs of the running stack
logs:
	docker compose logs -f

## Show container status
ps:
	docker compose ps

## Run every test suite inside the running dev containers (start `make dev-d` first)
test: test-backend test-agent test-frontend

test-backend:
	docker compose exec backend .venv/bin/pytest -q

test-agent:
	docker compose exec agent .venv/bin/pytest -q

test-frontend:
	docker compose exec frontend npm test -- --run
