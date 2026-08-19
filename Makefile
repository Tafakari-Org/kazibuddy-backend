# ─────────────────────────────────────────────────────────────────────────────
# KaziBuddy Backend — Makefile
# Usage: make <target>
# ─────────────────────────────────────────────────────────────────────────────

DC      := docker compose
PROD    := docker compose -f docker-compose.prod.yml
MANAGE  := $(DC) exec web python tafakari/manage.py
APP     ?= accounts   # default app for makemigrations (override: make migrations APP=jobs)

.DEFAULT_GOAL := help

.PHONY: help \
        up down restart build rebuild logs logs-web logs-celery \
        migrate migrations shell bash db-shell \
        seed seed-flush seed-jobs seed-jobs-flush seed-all seed-all-flush static \
        test lint \
        prod-up prod-down prod-deploy \
        clean

# ── Help ──────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "  KaziBuddy Backend"
	@echo ""
	@echo "  Dev"
	@echo "    make up              Start all services (detached)"
	@echo "    make down            Stop all services"
	@echo "    make restart         Restart web + celery (picks up code changes)"
	@echo "    make build           Build images without starting"
	@echo "    make rebuild         Force rebuild images and restart"
	@echo "    make logs            Tail all service logs"
	@echo "    make logs-web        Tail web (daphne) logs only"
	@echo "    make logs-celery     Tail celery logs only"
	@echo ""
	@echo "  Django"
	@echo "    make migrate         Apply all pending migrations"
	@echo "    make migrations      Create migrations  (APP=<name> to target one app)"
	@echo "    make shell           Open Django shell"
	@echo "    make bash            Open bash inside the web container"
	@echo "    make db-shell        Open psql inside the db container"
	@echo "    make static          Collect static files"
	@echo ""
	@echo "  Seed data"
	@echo "    make seed            Create seed users (skips existing)"
	@echo "    make seed-flush      Delete seed users and recreate from scratch"
	@echo "    make seed-jobs       Create seed job data (requires seed users)"
	@echo "    make seed-jobs-flush Delete seed jobs and recreate from scratch"
	@echo "    make seed-all        Run seed_data then seed_jobs"
	@echo "    make seed-all-flush  Flush and recreate all seed data"
	@echo ""
	@echo "  Quality"
	@echo "    make test            Run Django test suite"
	@echo "    make lint            Run flake8 linter inside container"
	@echo ""
	@echo "  Production"
	@echo "    make prod-up         Start prod services (detached)"
	@echo "    make prod-down       Stop prod services"
	@echo "    make prod-deploy     Run the full deploy script"
	@echo ""
	@echo "  Housekeeping"
	@echo "    make clean           Remove stopped containers and dangling images"
	@echo ""

# ── Dev lifecycle ─────────────────────────────────────────────────────────────

up:
	$(DC) up -d
	@echo ""
	@echo "  Services running:"
	@$(DC) ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

down:
	$(DC) down

restart:
	$(DC) restart web celery
	@echo "  web + celery restarted (code changes only)"
	@echo "  NOTE: for .env changes use 'make up' to recreate containers"

build:
	$(DC) build

rebuild:
	$(DC) up -d --build
	@echo "  Images rebuilt and services restarted"

logs:
	$(DC) logs -f

logs-web:
	$(DC) logs -f web

logs-celery:
	$(DC) logs -f celery

# ── Django management ─────────────────────────────────────────────────────────

migrate:
	$(MANAGE) migrate

migrations:
	$(MANAGE) makemigrations $(APP)

shell:
	$(MANAGE) shell

bash:
	$(DC) exec web bash

db-shell:
	$(DC) exec db psql -U postgres -d tafakaridb

static:
	$(MANAGE) collectstatic --noinput --clear

# ── Seed data ─────────────────────────────────────────────────────────────────

seed:
	$(MANAGE) seed_data

seed-flush:
	$(MANAGE) seed_data --flush

seed-jobs:
	$(MANAGE) seed_jobs

seed-jobs-flush:
	$(MANAGE) seed_jobs --flush

seed-all:
	$(MANAGE) seed_data
	$(MANAGE) seed_jobs

seed-all-flush:
	$(MANAGE) seed_data --flush
	$(MANAGE) seed_jobs --flush

# ── Quality ───────────────────────────────────────────────────────────────────

test:
	$(MANAGE) test --verbosity=2

lint:
	$(DC) exec web flake8 tafakari --max-line-length=120 --exclude=migrations,__pycache__

# ── Production ────────────────────────────────────────────────────────────────

prod-up:
	$(PROD) up -d

prod-down:
	$(PROD) down

prod-deploy:
	bash scripts/deploy.sh

# ── Housekeeping ──────────────────────────────────────────────────────────────

clean:
	docker container prune -f
	docker image prune -f
	@echo "  Pruned stopped containers and dangling images"
