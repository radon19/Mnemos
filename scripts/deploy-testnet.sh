#!/usr/bin/env bash
# Build and deploy the Mnemos contract to testnet. Idempotent: rerunning updates
# nothing that is already correct and prints the contract id.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "missing .env; copy .env.example and fill it in" >&2
  exit 1
fi
set -a
# shellcheck disable=SC1091
source .env
set +a

if [[ ! -f .secrets/accounts.json ]]; then
  echo "missing .secrets/accounts.json" >&2
  exit 1
fi

printf '\n== build contract ==\n'
(
  cd contracts/mnemos
  cargo near build non-reproducible-wasm
)

printf '\n== deploy and configure testnet ==\n'
(
  cd apps/broker
  uv sync --quiet
  uv run python ../../scripts/deploy_testnet.py "$@"
)
