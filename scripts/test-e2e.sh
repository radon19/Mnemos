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
  # The conftest derives the test database URL from the broker settings and
  # always targets a database whose name contains "test", so no secret has to
  # be echoed into the environment.
  uv run python -c "import os, subprocess; from sqlalchemy.engine import make_url; from mnemos_broker.config import get_settings; url = make_url(get_settings().database_url).set(database='mnemos_test'); subprocess.run(['alembic', 'upgrade', 'head'], env={**os.environ, 'DATABASE_URL': url.render_as_string(hide_password=False)}, check=True)"
  uv run pytest -q -m "integration" --no-header
)

section "web: Playwright end-to-end"
pnpm --filter @mnemos/web exec playwright test

printf '\nEnd-to-end suite passed.\n'
