# Progress

Updated: 2026-11-11

## Current phase

Phase 1 — scaffold. Next: Phase 2 contract.

## Phase checklist

- [x] Phase 0 — preflight, four testnet accounts created, NEAR AI key stored
- [ ] Phase 1 — scaffold, compose, CI, Makefile, PRODUCT.md, DESIGN.md
- [ ] Phase 2 — contract, unit and sandbox tests, testnet deploy
- [ ] Phase 3 — TS crypto, Python counterpart, shared vectors, interop
- [ ] Phase 4 — broker: DB, auth, vault, ask pipeline, TEE, filter, sweeper, tests
- [ ] Phase 5 — MCP server, agent CLI, tests, examples
- [ ] Phase 6 — web screens, Playwright, axe
- [ ] Phase 7 — red-team suite, demo, docs, Impeccable audit, verification

## Accounts (testnet)

Recorded in `.secrets/accounts.json` (never committed):

- contract: `mnemos-contract-76badc8e.testnet`
- owner: `mnemos-owner-76badc8e.testnet`
- agent: `mnemos-agent-76badc8e.testnet`
- broker: `mnemos-broker-76badc8e.testnet`

## Decisions so far

- NEAR AI model: `deepseek-ai/DeepSeek-V4.1-Flash-1017` (attestation/TEE-capable
  per models endpoint; $0.30/$1.20 per million tokens). Re-verify E2EE support
  with the SDK before locking.
- Wallet connection: `@hot-labs/near-connect` per current docs.near.org, not the
  deprecated wallet selector.
- Node 26.13, pnpm 12.15, Python 3.12.16 via uv, Rust 1.98.1, near-sdk 5.30.1.

## Exact commands to resume

```bash
cd /home/radon/HACKS/Mnemos
cat docs/PROGRESS.md
git log --oneline -10
```

## Open issues

- Confirm testnet faucet balances for all four accounts.
- Confirm E2EE/attestation support for the chosen model with a live SDK call.
