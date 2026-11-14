SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help install dev up down logs check test test-e2e demo demo-ready doctor record-demo deploy db-migrate broker-dev web-dev agent-key agent-api-setup agent-api-check agent-api-fund judging-check

help:
	@echo "Mnemos targets"
	@echo "  make install     Install Node, Python and Rust dependencies"
	@echo "  make dev         docker compose up --build (postgres, broker, web)"
	@echo "  make check       Static checks + unit tests (contract, crypto, broker, mcp, web)"
	@echo "  make test        Alias for check"
	@echo "  make test-e2e    Contract sandbox tests, full broker tests, Playwright"
	@echo "  make demo        Scripted end-to-end demo against the deployed contract"
	@echo "  make demo-ready  Configure and start the guarded laptop browser demo"
	@echo "  make doctor      Check local services and real testnet bindings"
	@echo "  make record-demo Record the real browser demo to artifacts/demo"
	@echo "  make agent-key   Provision the testnet agent's restricted runtime key"
	@echo "  make agent-api-setup Create real Agent API wallets and signed policies"
	@echo "  make agent-api-check Verify live destination/limit/revoked-grant refusals"
	@echo "  make agent-api-fund Print a 1Click address for real Base USDC funding"
	@echo "  make judging-check Verify live AI, nonce rejection, keys and API policies"
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
	pnpm --filter @mnemos/crypto build
	pnpm --filter @mnemos/mcp build
	docker compose up -d postgres broker
	cd apps/broker && uv run python ../../scripts/demo.py

agent-key:
	uv run --project apps/broker python scripts/laptop.py configure

agent-api-setup:
	uv run --project apps/broker python scripts/agent_api.py setup

agent-api-check:
	uv run --project apps/broker python scripts/agent_api.py check

agent-api-fund:
	uv run --project apps/broker python scripts/agent_api.py funding base

judging-check:
	uv run --project apps/broker python scripts/judging-check.py

demo-ready:
	uv run --project apps/broker python scripts/laptop.py configure
	docker compose up -d --build --wait
	$(MAKE) doctor

doctor:
	uv run --project apps/broker python scripts/laptop.py doctor

record-demo:
	node scripts/record-demo.mjs

deploy:
	./scripts/deploy-testnet.sh

broker-dev:
	cd apps/broker && uv run uvicorn mnemos_broker.main:app --reload --port 8000

web-dev:
	pnpm --filter @mnemos/web dev
