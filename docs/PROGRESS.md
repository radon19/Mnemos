# Progress

Updated: 2026-11-11

## Current phase

Phase 4 — broker. Phases 0–3 are complete: the contract is deployed and the
crypto packages pass cross-language vectors.

## Phase checklist

- [x] Phase 0 — preflight, four testnet accounts created, NEAR AI key stored
- [x] Phase 1 — scaffold, compose, CI, Makefile, PRODUCT.md, DESIGN.md
- [x] Phase 2 — contract, unit and sandbox tests, testnet deploy
- [x] Phase 3 — TS crypto, Python counterpart, shared vectors, interop
- [ ] Phase 4 — broker: DB, auth, vault, ask pipeline, TEE, filter, sweeper, tests
- [ ] Phase 5 — MCP server, agent CLI, tests, examples
- [ ] Phase 6 — web screens, Playwright, axe
- [ ] Phase 7 — red-team suite, demo, docs, Impeccable audit, verification

## Testnet deployment

Recorded in `.secrets/deployment.json` (never committed).

- contract: `mnemos-contract-76badc8e.testnet`
- owner: `mnemos-owner-76badc8e.testnet`
- agent: `mnemos-agent-76badc8e.testnet`
- broker: `mnemos-broker-76badc8e.testnet`
- broker key fingerprint: `f15d7141fd619dd65cc7fac29cb5a3a11d642aaa47f6a00f757bfedf9e6eb0a4`
- wasm SHA-256: `aa18000844e238db3c74f9cd1a384e0abc8caac30e73f46ea0b446035082f4c5`
- agent credit: 5 NEAR

Transactions:

| Step | Transaction |
| --- | --- |
| deploy | `DtQpji748V8hujxy9hrm4GppcPv21PNJQtqi4pXJP1Jh` |
| init | `EycciGFHbRS7CJS16K1DGrtRV5PzH1CHLgDJcoy3ALjT` |
| set_broker | `2AQ12NtKN6EUHXdippirBDtbTry2GgRgdx9BiZNb8q5y` |
| deposit_credit | `APgqZPysbq3sYq3BRU6NxrWvGxJHXHyfvQahCpgP4hB` |

Verified with independent view calls:

```text
get_config  -> owner mnemos-owner-76badc8e.testnet, paused false,
               request_ttl_ns 600000000000, day_ns 86400000000000
get_broker  -> broker mnemos-broker-76badc8e.testnet,
               fingerprint f15d7141fd619dd65cc7fac29cb5a3a11d642aaa47f6a00f757bfedf9e6eb0a4
credit_of   -> 5000000000000000000000000
```

## Phase 2 verification

- `cargo test --lib`: 13 passed.
- `cargo test --test integration`: 2 passed. Covers revoked, expired, wrong scope,
  cap hit, re-grant reset, insufficient credit, double receipt, non-broker caller,
  refund, request expiry, paused, and withdrawal failure rollback.
- `cargo clippy --all-targets -- -D warnings`: clean.
- `cargo near build non-reproducible-wasm`: 252.7 KB wasm, checksum recorded above.
- Broker Python: `ruff check`, `ruff format --check`, `mypy --strict` clean.
- Broker signer view calls and all four deploy transactions confirmed on testnet.

## Phase 3 verification

- TypeScript `@mnemos/crypto`: build, typecheck and lint clean; 21 tests passed.
- Python `mnemos_broker.crypto`: `ruff` clean, `mypy --strict` clean; 10 tests passed.
- Three committed vectors in `packages/crypto-vectors/vectors.json` are
  re-encrypted byte for byte by both languages and decrypted by both the owner
  KEK and the broker X25519 key.
- Tamper tests reject flipped item ciphertext, changed scope, owner or item id,
  wrong passphrase, wrong salt, flipped owner/broker wrapped DEK, and a
  mismatched content hash.


## Decisions so far

- NEAR AI model: `deepseek-ai/DeepSeek-V4.1-Flash-1017` (attestation/TEE-capable
  per models endpoint; $0.30/$1.20 per million tokens). Re-verify E2EE support
  with the SDK before locking.
- Wallet connection: `@hot-labs/near-connect` per current docs.near.org, not the
  deprecated wallet selector.
- Node 26.13, pnpm 12.15, Python 3.12.16 via uv, Rust 1.98.1, near-sdk 5.30.1.
- Contract uses `cargo near build non-reproducible-wasm` because the plain
  command requires a TTY in this environment.

## Exact commands to resume

```bash
cd /home/radon/HACKS/Mnemos
cat docs/PROGRESS.md
git log --oneline -10
```

## Open issues

- Confirm E2EE/attestation support for the chosen model with a live SDK call
  during Phase 4.
- Day-rollover reset is unit-tested only; the sandbox `fast_forward(86_400)`
  path takes ~14 minutes and was removed from the integration suite. Re-grant
  reset is covered in the sandbox.
