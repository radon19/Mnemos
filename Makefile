SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help install dev up down logs check test test-e2e demo deploy db-migrate broker-dev web-dev

help:
	@echo "Mnemos targets"
	@echo "  make install     Install Node, Python and Rust dependencies"
	@echo "  make dev         docker compose up --build (postgres, broker, web)"
	@echo "  make check       Static checks + unit tests (contract, crypto, broker, mcp, web)"
	@echo "  make test        Alias for check"
	@echo "  make test-e2e    Contract sandbox tests, full broker tests, Playwright"
	@echo "  make demo        Scripted end-to-end demo against the deployed contract"
	@echo "  make deploy      Build and deploy the contract to testnet"
	@echo "  make db-migrate  Run Alembic migrations against the compose Postgres"

install:
	pnpm install
	cd apps/broker && uv sync
	cd contracts/mnemos && cargo fetch

dev: up
up:
	docker compose up -d --build
down:
	docker compose down
logs:
	docker compose logs -f

db-migrate:
	docker compose exec broker alembic upgrade head

check:
	./scripts/check.sh

test: check

test-e2e:
	./scripts/test-e2e.sh

demo:
	cd apps/broker && uv run python ../../scripts/demo.py

deploy:
	./scripts/deploy-testnet.sh

broker-dev:
	cd apps/broker && uv run uvicorn mnemos_broker.main:app --reload --port 8000

web-dev:
	pnpm --filter @mnemos/web dev
