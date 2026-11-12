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

## D-010 — Agent request signature format

**Context.** The brief requires the agent to sign each `/v1/ask` request. The
signature has to bind the request id, the question, a nonce and the broker, or
a captured signature could be replayed against a different question.

**Decision.** The agent signs this canonical UTF-8 message with Ed25519 over
SHA-256 of the message bytes:

```text
mnemos:v1:ask|{req_id}|{sha256(question)}|{nonce_hex}|{recipient}
```

`nonce_hex` is 32 random bytes in lowercase hex. `recipient` is the broker
recipient (`host:port`). The broker additionally verifies that the signing
public key belongs to the requesting agent account through
`view_access_key`, and that the request on chain carries the same `q_hash`,
which is `sha256(question UTF-8 || 32 nonce bytes)`. The question text itself
is never written to the database; only `q_hash` is.

## D-011 — Owner sessions are HMAC-signed cookies, not server-side sessions

**Context.** The brief asks for a short-lived HttpOnly session cookie after a
NEP-413 login. The broker is a single service with a Postgres database.

**Decision.** The session cookie carries an HMAC-SHA256 signed payload with
`account`, `iat`, `exp` and `demo`, keyed by `SESSION_SECRET`. It is
HttpOnly, SameSite=Strict, and secure whenever `SESSION_COOKIE_SECURE=true`.
The NEP-413 challenge itself is stored in Postgres with the exact message that
the wallet displayed, so the broker verifies the bytes the user actually
signed. Challenges are single use and expire after five minutes. Signing out
deletes the cookie; there is no server-side session table to leak.

## D-012 — Prices are stored as numeric(78, 0)

**Context.** NEAR prices are u128 yoctoNEAR. The contract allows a price of up
to 1000 NEAR, which is 10^24 yoctoNEAR and does not fit in a signed 64-bit
integer. Storing the price as `bigint` silently truncated every realistic
price.

**Decision.** `read_requests.price` is `numeric(78, 0)` with a
`YoctoAmount` type decorator that keeps exact Python integers on both sides of
the boundary. The activity API always renders the amount as a decimal string,
never as a float.

## D-013 — Two broker tables beyond the brief

**Context.** The brief lists four tables. The product needs two more to work
without weakening any guarantee.

**Decision.**

- `owner_accounts` stores the per-owner PBKDF2 salt. The salt is not secret
  (it is a KDF salt, not a key), but it must be stable: re-using a different
  salt with the same passphrase would silently break every existing item, so
  the broker rejects a mismatched salt instead of overwriting it.
- `read_requests` additionally stores `price`, `receipt_tx_hash` and
  `refund_tx_hash` so the activity screen can link a read to its settlement
  transaction without an indexer.

No plaintext memory, question text or answer text is ever stored. The broker
stores ciphertext, nonces, wrapped DEKs, hashes, identifiers and error codes
only.

## D-014 — The MCP server finds its own request id on chain

**Context.** `request_read` returns the new request id as the return value of
the function call. Parsing that value out of a NEAR transaction receipt is
version specific and easy to get wrong, and the id is not returned in a place
the RPC makes easy to read.

**Decision.** The MCP server reads `get_config().next_request_id` before and
after the transaction and selects the request whose `q_hash` matches the one
it sent. Request ids are sequential, so the new request is always inside that
window, and matching on the hash keeps the lookup correct when another agent
creates a request at the same time. The method never guesses an id.

## D-015 — The MCP server is the only place that signs for the agent

**Context.** An agent key that can call `request_read` could also be used to
sign arbitrary transactions if it leaked.

**Decision.** The MCP server holds the agent key in its process environment
only. It uses the key for exactly two things: signing the `request_read`
transaction and signing the canonical ask message for `/v1/ask`. The broker
verifies that the signing key belongs to the agent account with
`view_access_key` before serving a read, and the contract charges the agent
before the request exists, so a leaked key cannot read the vault directly.

## D-016 — near-api-js is pinned to 7.4.0

**Context.** The workspace enforces a minimum release age for npm packages.
`near-api-js` 7.5.0 and 7.5.1 were published on the day of the build and are
inside that window, so the lockfile would need an explicit exclusion for them.

**Decision.** Pin `near-api-js` 7.4.0, the newest release that is outside the
minimum-release-age window. The API used by the MCP server (`Account`,
`JsonRpcProvider`, `actions.functionCall`, `KeyPair.fromString`) is identical
in 7.4.0, all 32 tests pass against it, and the lockfile passes the
supply-chain policy with no exclusions.

## D-017 — The contract lists the owner's grants

**Context.** The Grants screen has to show every grant an owner gave. With
only `get_grant(owner, agent)` the browser could show a grant it knew the
agent for, which meant keeping the list in local storage and losing it in
another browser.

**Decision.** Add a `grants_by_owner(owner)` view that returns the owner's
grants, newest expiry first. The list is bounded by `MAX_GRANTS_PER_OWNER`,
so it cannot grow without limit, and it is a view: it costs nothing to keep.
The owner interface reads the chain and nothing else.

## D-018 — The broker keeps a retention window, not everything

**Context.** The brief asks for bounded collections. The broker's tables were
growing: sign-in challenges were never removed, audit events accumulated
forever and deleted vault items stayed as soft deletes.

**Decision.** A retention job runs every hour and removes what is past its
useful life: expired challenges after an hour, audit events after a month,
deleted vault items after a month and read requests after a quarter. Nothing a
read depends on is deleted, because the chain keeps the receipt ring and the
activity feed merges both.

## D-019 — The red-team run is a background job

**Context.** Six attacks are six model calls, which takes about forty
seconds. A single HTTP request that long is cut by proxies and leaves the
browser waiting.

**Decision.** `POST /v1/redteam/run` starts a job and returns its id;
`GET /v1/redteam/run/{id}` reports the state and, when it is done, the
report. The browser polls every two seconds and says how long the run takes.
The run itself is unchanged: the same production prompt, the same filter, no
chain writes.

## D-020 — The browser refuses to encrypt for an unverified broker

**Context.** The crypto section of the brief requires the web app to check
that the broker's key fingerprint equals the one registered on chain before it
encrypts. A note sealed for the wrong broker can never be read back.

**Decision.** The vault reads the served fingerprint and the registered one.
If they differ, or if the chain cannot be read to check, the browser refuses
to encrypt and says why. The Setup screen shows the same comparison, so the
owner can see it before it matters.

## D-021 — The owner reads their own vault in the browser

**Context.** The broker stores every item wrapped twice: once for the owner
and once for the broker. Until now the browser only ever wrote them.

**Decision.** The owner wrap is enough to open an item locally, so the Vault
screen offers a Read action that decrypts with the passphrase in the tab.
Nothing is decrypted on the server, the passphrase is never stored, and the
broker never sees the plaintext. The broker does not hand out its own wrap,
because the owner does not need it.
