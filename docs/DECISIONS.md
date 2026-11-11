# Decisions

Recorded as decisions are made. Newest last.

## D-001 — Monorepo with pnpm workspaces and uv

**Context.** The brief fixes the repository layout: Rust contract, Python broker,
TypeScript MCP server and web app, shared crypto packages.

**Decision.** One repository. pnpm workspaces for `apps/web`, `apps/mcp`,
`packages/crypto`, `packages/crypto-vectors`. The broker is a standalone uv
project in `apps/broker` with its own lockfile. The contract is a standalone
Cargo crate.

**Consequences.** One `make check` can orchestrate every language. Docker builds
use the monorepo root for the web app and the broker directory for the broker.

## D-002 — Wallet connection via NEAR Connect

**Context.** docs.near.org states that `@near-wallet-selector/*` is deprecated
and recommends `@hot-labs/near-connect` for new apps.

**Decision.** Use `@hot-labs/near-connect` (0.12.x) for owner wallet connection
and NEP-413 `signMessage`, with `near-api-js` 7.5.x for view calls and
transaction submission. Do not use the deprecated wallet selector or key-store
patterns.

## D-003 — Model

**Context.** The NEAR AI Cloud models endpoint lists 63 models. The brief asks
for the best current instruct model that supports E2EE.

**Decision.** `deepseek-ai/DeepSeek-V4.1-Flash-1017`. The models endpoint marks it
with model attestation and TEE metadata, and it is priced at $0.30 / $1.20 per
million tokens, which keeps the demo within the supplied credit. The SDK's
preflight verification is the authority: if it rejects E2EE for this model, the
broker falls back to the next attested model from a configured allowlist and
records the reason.

## D-004 — Broker signs NEAR transactions directly

**Context.** The broker must call `record_receipt`, `refund` and
`expire_request` autonomously. There is no maintained Python NEAR SDK that the
team can vouch for at build time.

**Decision.** Implement a small, documented NEAR transaction signer in Python
using `cryptography` Ed25519 and Borsh, against the public JSON-RPC
`query`/`block`/`send_tx` methods. It supports FunctionCall actions only. The
encoding is covered by tests with fixed vectors and verified on testnet.

## D-005 — Broker key fingerprint

**Decision.** `fingerprint = lowercase hex SHA-256(raw 32-byte X25519 public
key)`. The owner registers it on-chain with `set_broker`. The web app refuses to
encrypt an item when the broker's served public key fingerprint differs from the
on-chain value.

## D-006 — Demo signer is local-only and explicit

**Context.** Browser wallet availability on testnet is not guaranteed during
judging or Playwright runs.

**Decision.** The web app supports two owner sign-in paths: NEAR Connect
(NEP-413) and, only when `DEMO_OWNER_SECRET_KEY` is set server-side and
`NEXT_PUBLIC_DEMO_MODE=true`, a clearly labelled local demo signer. The demo
signer is disabled by default, never exposed to the client, documented as a
local-only convenience, and never used for production claims.
