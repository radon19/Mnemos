#!/usr/bin/env bash
# Static checks and unit tests. No network, no live model, no chain writes.
set -euo pipefail
cd "$(dirname "$0")/.."

section() { printf '\n== %s ==\n' "$1"; }

section "contract: format, clippy, unit tests"
(
  cd contracts/mnemos
  cargo fmt --check
  cargo clippy --all-targets -- -D warnings
  cargo test --lib
)

section "crypto: build, typecheck, unit + vector tests"
pnpm --filter @mnemos/crypto build
pnpm --filter @mnemos/crypto test

section "broker: ruff, mypy, unit tests"
(
  cd apps/broker
  uv run ruff check .
  uv run ruff format --check .
  uv run mypy src
  uv run pytest -q -m "not integration and not live"
)

section "mcp: typecheck, lint, tests"
pnpm --filter @mnemos/mcp typecheck
pnpm --filter @mnemos/mcp lint
pnpm --filter @mnemos/mcp test

section "web: typecheck, lint, tests"
pnpm --filter @mnemos/web typecheck
pnpm --filter @mnemos/web lint
pnpm --filter @mnemos/web test

printf '\nAll checks passed.\n'
