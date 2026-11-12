# Progress

Updated: 2026-11-11

## Current phase

All seven phases are complete. The contract is deployed on NEAR testnet, the
broker is verified against live NEAR AI Cloud with E2EE and a TEE attestation,
the MCP server talks to the real chain, the web app passes its accessibility
suite at 390, 768 and 1440 pixels, and the scripted demo runs the whole
product story against the deployed contract.

## Phase checklist

- [x] Phase 0 — preflight, four testnet accounts created, NEAR AI key stored
- [x] Phase 1 — scaffold, compose, CI, Makefile, PRODUCT.md, DESIGN.md
- [x] Phase 2 — contract, unit and sandbox tests, testnet deploy
- [x] Phase 3 — TS crypto, Python counterpart, shared vectors, interop
- [x] Phase 4 — broker: DB, auth, vault, ask pipeline, TEE, filter, sweeper, tests
- [x] Phase 5 — MCP server, agent CLI, tests, examples
- [x] Phase 6 — web screens, Playwright, axe
- [x] Phase 7 — red-team suite, demo, docs, Impeccable audit, verification

## Testnet deployment

Recorded in `.secrets/deployment.json` (never committed).

- contract: `mnemos-contract-76badc8e.testnet`
- owner: `mnemos-owner-76badc8e.testnet`
- agent: `mnemos-agent-76badc8e.testnet`
- broker: `mnemos-broker-76badc8e.testnet`
- broker key fingerprint: `f15d7141fd619dd65cc7fac29cb5a3a11d642aaa47f6a00f757bfedf9e6eb0a4`
- wasm SHA-256: `8caf329964afaedd2df7c07a4c26c9c55de8829662abbb61dcbf274a5adf0907`
- agent credit: 5 NEAR

Transactions:

| Step | Transaction |
| --- | --- |
| deploy | `DtQpji748V8hujxy9hrm4GppcPv21PNJQtqi4pXJP1Jh` |
| deploy (with `grants_by_owner`) | `85mtN5AaSurqbmyy6CHP1hZ3Gwiqe3s39NSRTf3STARY` |
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
- `cargo near build non-reproducible-wasm`: 260.7 KB wasm, checksum recorded above.
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


## Phase 4 verification

- `ruff check src tests`, `ruff format --check src tests`, `mypy --strict src`:
  clean (37 source files, 20 test files).
- Unit tests: 68 passed. Integration tests against Postgres 16: 54 passed.
- Schema: Alembic `0001_initial` creates `owner_accounts`, `vault_items`,
  `read_requests`, `auth_challenges`, `audit_events`. `alembic upgrade head`
  is idempotent and runs on container start.
- Live NEAR AI Cloud: one E2EE completion with
  `deepseek-ai/DeepSeek-V4.1-Flash-1017` verified with `provider_tee`
  signature, `tcb_status UpToDate`, `gpu_evidence verified`,
  `compose_manager_verified true`. Full output in `docs/VERIFICATION.md`.
- The broker refuses to answer before verification succeeds; there is no
  unverified fallback path.

### Phase 4 implementation notes

- Ask pipeline order: signature → on-chain key ownership → request binding
  (`q_hash`) → database claim → grant and scope checks → decrypt → rank →
  infer → filter → settle. Failures before the claim never refund, so an
  attacker cannot cancel someone else's pending read.
- The claim is a primary-key insert on `read_requests`, so two concurrent
  calls for the same request id produce exactly one served read.
- The output filter blocks any 12-word contiguous run shared with a decrypted
  memory item, including runs hidden in base64 or hex, then retries once with
  a stricter prompt and refunds if the second attempt still leaks.
- Two broker tables beyond the brief: `owner_accounts` (per-owner PBKDF2 salt)
  and settlement hashes on `read_requests`. Recorded as D-013.

## Phase 5 verification

```text
$ cd apps/mcp && pnpm typecheck
$ tsc -p tsconfig.json --noEmit

$ cd apps/mcp && pnpm lint
$ eslint .

$ cd apps/mcp && pnpm test
$ vitest run

 RUN  v5.1.0 /home/radon/HACKS/Mnemos/apps/mcp

 Test Files  5 passed (5)
      Tests  32 passed (32)
   Start at  12:49:16
   Duration  1.23s (tests 75%, import 22%, other 3%)
```

Live against NEAR testnet with the real agent account:

```text
$ uv run --project apps/broker python scripts/live-mcp-check.py
$ mnemos-agent credit
{
  "agent": "mnemos-agent-76badc8e.testnet",
  "credit_yocto": "5000000000000000000000000",
  "credit_near": "5"
}
$ mnemos-agent grants --owner mnemos-owner-76badc8e.testnet
E_GRANT_NOT_FOUND: mnemos-owner-76badc8e.testnet has no grant for mnemos-agent-76badc8e.testnet
The owner has not granted this agent access yet. Ask them to create a grant for this agent account.
```

The `grants` command reports the honest state of the chain: no grant exists
yet, and the error carries the stable code and the next action.

## Phase 6 verification

- `tsc --noEmit`, `eslint .` and `next build` are clean.
- Playwright with axe-core: 27 tests pass at 1440, 768 and 390 pixels, covering
  all seven screens, horizontal overflow and the navigation.
- The Impeccable detector reports no primary finding on any screen. The
  findings that existed were fixed: kicker labels, the cream background,
  cramped padding, low-contrast disabled buttons, a hydration error and a
  horizontal overflow at 768. One advisory finding was kept on purpose and is
  recorded in `docs/DESIGN_REVIEW.md`.
- Screenshots at 1440 and 390 in both themes were reviewed.

### Phase 6 implementation notes

- Next.js 16 App Router, TypeScript strict, Tailwind 4 tokens, TanStack Query
  for server state, `@hot-labs/near-connect` for the wallet and NEP-413
  signing.
- The vault item is sealed in the browser with `@mnemos/crypto` before it is
  sent. The passphrase is held in a ref for the lifetime of the tab and is
  never stored or sent.
- The owner session comes from the broker as an HttpOnly cookie; the browser
  never sees a key.
- A local demo signer exists behind `DEMO_OWNER_SECRET_KEY` and
  `NEXT_PUBLIC_DEMO_MODE` so the flow can be shown without a browser wallet.
  It is disabled by default and the UI labels it as a demo session.

## Phase 7 verification

- `make check` passes: the contract, the crypto packages, the broker, the MCP
  server and the web app are all clean.
- `make test-e2e` passes: 2 sandbox tests, 62 broker integration tests against
  Postgres and 36 Playwright tests across 1440, 768 and 390 pixels.
- `docker compose up -d --build` brings up Postgres, the broker and the web app
  healthy. The web image runs the Next standalone server; the broker image
  runs its Alembic migrations before serving.
- `make demo` runs the whole story: NEP-413 sign-in, an encrypted note, a
  grant, an MCP read with a verified `provider_tee` attestation, the receipt on
  chain, the red-team set, the revoke, and the same read denied with
  `E_GRANT_REVOKED`.
- The red-team suite against a model that tries to comply: the bulk attacks are
  withheld and refunded, and the report names the residual risk for the narrow
  attacks instead of claiming they were blocked.
- The live red-team run against the real model: six attacks, no answer carried
  twelve consecutive words of the memory.

## Phase 10 — the missing features

Everything the brief describes and the build did not have is now in place.

- The contract gained `grants_by_owner`, so the Grants screen lists the
  owner's grants from the chain. Unit tested, checked in the sandbox and
  redeployed to testnet (`85mtN5AaSurqbmyy6CHP1hZ3Gwiqe3s39NSRTf3STARY`).
- The owner can read their own notes in the browser: the vault is opened with
  the owner wrap and the passphrase, in the tab, and the broker never sees
  the plaintext.
- The browser refuses to encrypt when the broker's key does not match the one
  registered on chain, and says why.
- Grants can be edited, and the contract has a pause switch in the interface.
- Every hash has a copy control.
- The red-team run is a background job: the endpoint returns immediately and
  the browser polls, so no proxy cuts a forty-second request.
- The broker's tables have a retention window, the logs are all JSON, the
  broker image runs as a non-root user, compose caps the resources, and CI
  runs `make check` the way a reviewer does.

```text
$ cd apps/broker && uv run pytest -q -m integration
64 passed, 74 deselected in 10.18s
```

## Phase 9 — responsive

The ledger tables were the one thing the redesign broke on a phone: six columns
at 390 pixels is 411 pixels of table, and the card clipped the rest, so the
receipt hash and the delete control were unreachable. The tables are now one
component — a real table from `md` up, and below that a stack of records, one
per read, each field labelled the way a receipt is labelled.

Also fixed: the navigation bar overflowed at 768 pixels, the grant form
squeezed four fields into two columns on a phone, the revoke dialog could run
past the bottom of a short screen, several touch targets were under 44
pixels, and the owner account in the bar was truncated in a way that made a
screen reader read the truncated string.

A responsive suite now walks every screen at thirteen widths from 320 to 1920
pixels, signs in so the screens carry their real content, and fails on
sideways scrolling, clipped text or a touch target under 30 pixels.

```text
$ cd apps/web && pnpm exec playwright test
  81 passed (8.0m)
```

## Decisions so far
- NEAR AI model: `deepseek-ai/DeepSeek-V4.1-Flash-1017` (attestation/TEE-capable
  per models endpoint; $0.30/$1.20 per million tokens). E2EE and provider TEE
  attestation confirmed by a live SDK call in Phase 4.
- Wallet connection: `@hot-labs/near-connect` per current docs.near.org, not the
  deprecated wallet selector.
- Node 26.13, pnpm 12.15, Python 3.12.16 via uv, Rust 1.98.1, near-sdk 5.30.1.
- Contract uses `cargo near build non-reproducible-wasm` because the plain
  command requires a TTY in this environment.
- Agent ask signature: Ed25519 over
  `mnemos:v1:ask|{req_id}|{sha256(question)}|{nonce_hex}|{recipient}` (D-010).
- Owner session: HMAC-signed HttpOnly SameSite=Strict cookie (D-011).
- Prices stored as `numeric(78, 0)` because NEAR prices are u128 (D-012).

## Exact commands to resume

```bash
cd /home/radon/HACKS/Mnemos
cat docs/PROGRESS.md
git log --oneline -10
```

## Open issues

- Day-rollover reset is unit-tested only; the sandbox `fast_forward(86_400)`
  path takes ~14 minutes and was removed from the integration suite. Re-grant
  reset is covered in the sandbox.
- Rate limiting and the SSE activity stream are single-instance (in-process).
  A multi-replica deployment needs a shared limiter and a shared bus.
- The sweeper can only expire requests the broker has already seen; a request
  created on chain and never sent to `/v1/ask` needs an indexer or an agent
  that calls `expire_request` itself.
- The red-team screen reports paraphrase as a residual risk. Stopping that
  class needs a semantic check, not a lexical one; the current mitigation is
  the price and the daily cap.
- The demo signer exists for environments without a browser wallet. It is
  disabled unless `DEMO_OWNER_SECRET_KEY` and `NEXT_PUBLIC_DEMO_MODE=true`
  are both set.

## Phase 8 — frontend redesign

The owner asked for a redesign based on a marketing reference: a light page
lit from behind, one vivid accent, a floating navigation bar, a headline built
around a real number, and a row of figure cards. The information architecture
did not change; the visual world did, and `DESIGN.md` was rewritten to match.

- The landing page reads the real figures from the contract when it loads:
  earnings, the number of served reads, the price per read, the number of
  requests created and the broker fingerprint. There is no invented number and
  no testimonial; the quote cards hold real outputs (the latest receipt, the
  contract's own panic text after a revoke, the broker's published key).
- The app screens moved from a left rail to a floating navigation bar, from
  hairline rules to white cards with soft layered shadows, and from square
  buttons to pills.
- Typography is now Bricolage Grotesque, Instrument Sans and IBM Plex Mono.
- The colour tokens were renamed and a test now fails when the app uses a
  colour utility that the theme does not define. That test exists because the
  rename silently left one chip rendering ink-on-ink.
- Fixed while redesigning: pill buttons had no vertical padding, prose ran the
  full width of the page, the navigation overflowed at 768, the mobile menu
  links did not wrap, and the mobile menu unmounted on click, which cancelled
  the navigation.
- The detector findings that remain are deliberate and are recorded in
  `docs/DESIGN_REVIEW.md`: the violet ambient light and the accent colour come
  from the reference the owner chose.

