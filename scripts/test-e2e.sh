#!/usr/bin/env bash
# Integration tests: contract sandbox, broker against real Postgres, Playwright.
set -euo pipefail
cd "$(dirname "$0")/.."

section() { printf '\n== %s ==\n' "$1"; }

section "contract: near-workspaces sandbox tests"
(
  cd contracts/mnemos
  cargo test --test integration -- --nocapture
)

section "broker: integration tests against Postgres"
docker compose up -d postgres
(
  cd apps/broker
  export DATABASE_URL="${TEST_DATABASE_URL:-postgresql+asyncpg://mnemos:${POSTGRES_PASSWORD:-mnemos}@localhost:5432/mnemos_test}"
  uv run pytest -q -m "integration" --no-header
)

section "web: Playwright end-to-end"
pnpm --filter @mnemos/web exec playwright test

printf '\nEnd-to-end suite passed.\n'
