.DEFAULT_GOAL := help

COMPOSE_PROD := docker compose -f docker-compose.yml
COMPOSE_DEV  := docker compose -f docker-compose.yml -f docker-compose.dev.yml

.PHONY: help \
        dev-build dev-up dev-up-d dev-down dev-logs dev-restart \
        prod-build prod-up prod-up-d prod-down prod-logs prod-restart \
        down clean

help:
	@echo "Dev (hot-reload, Vite dev server):"
	@echo "  make dev-build     build the dev images"
	@echo "  make dev-up        build + start dev stack (foreground)"
	@echo "  make dev-up-d      build + start dev stack (detached)"
	@echo "  make dev-down      stop the dev stack"
	@echo "  make dev-logs      follow dev stack logs"
	@echo "  make dev-restart   dev-down + dev-up-d"
	@echo ""
	@echo "Prod-parity (lean images, no reload):"
	@echo "  make prod-build    build the prod-parity images"
	@echo "  make prod-up       build + start prod-parity stack (foreground)"
	@echo "  make prod-up-d     build + start prod-parity stack (detached)"
	@echo "  make prod-down     stop the prod-parity stack"
	@echo "  make prod-logs     follow prod-parity stack logs"
	@echo "  make prod-restart  prod-down + prod-up-d"
	@echo ""
	@echo "  make down          stop both stacks"
	@echo "  make clean         stop both stacks and remove volumes (deletes local Postgres data)"

dev-build:
	$(COMPOSE_DEV) build

dev-up:
	$(COMPOSE_DEV) up --build

dev-up-d:
	$(COMPOSE_DEV) up --build -d

dev-down:
	$(COMPOSE_DEV) down

dev-logs:
	$(COMPOSE_DEV) logs -f

dev-restart: dev-down dev-up-d

prod-build:
	$(COMPOSE_PROD) build

prod-up:
	$(COMPOSE_PROD) up --build

prod-up-d:
	$(COMPOSE_PROD) up --build -d

prod-down:
	$(COMPOSE_PROD) down

prod-logs:
	$(COMPOSE_PROD) logs -f

prod-restart: prod-down prod-up-d

down:
	-$(COMPOSE_DEV) down
	-$(COMPOSE_PROD) down

clean:
	-$(COMPOSE_DEV) down -v
	-$(COMPOSE_PROD) down -v
