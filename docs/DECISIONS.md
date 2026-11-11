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

## D-007 — Build with `cargo near build non-reproducible-wasm` locally

**Context.** `cargo near build` prompts through a TTY in this environment and
fails with "The input device is not a TTY" when run from an agent shell.

**Decision.** Local and testnet deployment use `cargo near build
non-reproducible-wasm`. The artifact is pinned in `docs/VERIFICATION.md` by
SHA-256. Reproducible builds remain available for a CI release job that has a
TTY-free cargo-near configuration; they are not required for the hackathon
deployment.

## D-008 — Day-boundary behaviour is unit-tested; sandbox covers re-grant reset

**Context.** Advancing the sandbox past a UTC day boundary with
`fast_forward(86_400)` took about 832 seconds because it crosses many epochs.

**Decision.** The next-day cap reset is covered by the unit test
`daily_cap_blocks_then_resets_next_day`, which sets `block_timestamp` directly.
The `near-workspaces` suite covers cap exhaustion and verifies that re-creating
a grant resets usage. This keeps the integration suite under a minute without
dropping behavioural coverage.

## D-009 — Envelope formats and cross-language vector strategy

**Context.** The brief fixes AES-256-GCM, PBKDF2-HMAC-SHA256 at 600000
iterations, X25519, and HKDF-SHA256, but leaves the byte layouts of the wrapped
DEKs and the broker-wrap AAD open.

**Decision.**

- Item: 12-byte nonce stored separately, ciphertext||tag in `ciphertext`, AAD
  `mnemos:v1|{owner}|{scope}|{item_id}`.
- Owner-wrapped DEK: `nonce(12) | ciphertext(32) | tag(16)`; AAD
  `mnemos:v1:wrap-owner|{item_id}`.
- Broker-wrapped DEK: `ephemeral_public(32) | nonce(12) | ciphertext(32) |
  tag(16)`; AAD `mnemos:v1:wrap-broker|{item_id}`; HKDF salt absent (RFC 5869
  HashLen zeroes), info `mnemos:v1:wrap-broker`.
- `content_hash` is lowercase hex SHA-256 of the stored ciphertext (including
  the GCM tag), so the broker can verify stored bytes without seeing plaintext.
- Broker fingerprint remains lowercase hex SHA-256 of the raw 32-byte X25519
  public key.

**Interop proof.** `packages/crypto-vectors/vectors.json` contains fixed
randomness so both implementations must produce the exact same ciphertext,
wraps and hash. TS has 21 tests and Python has 10; both re-encrypt every vector
byte for byte and decrypt it with the owner passphrase and with the broker
private key. Because the produced bytes are identical, either language can
consume the other's envelopes.


