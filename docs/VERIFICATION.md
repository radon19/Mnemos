# Verification

Real command output, copied from the machine that built Mnemos. Nothing here is
reconstructed or paraphrased.

## Whole repository

```text
$ ./scripts/check.sh
== contract: format, clippy, unit tests ==
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.20s
    Finished `test` profile [unoptimized + debuginfo] target(s) in 0.21s
     Running unittests src/lib.rs (target/debug/deps/mnemos_contract-f2c6d7952d889d1c)
running 13 tests
test tests::invalid_inputs_are_rejected ... ok
test tests::broker_and_grant_are_registered_and_viewed ... ok
test tests::expiry_restores_credit_and_is_permissionless ... ok
test tests::grant_upsert_resets_usage_and_unrevokes ... ok
test tests::refund_restores_credit_and_cap ... ok
test tests::non_broker_cannot_record_or_refund ... ok
test tests::pause_blocks_new_grants_and_reads ... ok
test tests::read_escrows_credit_and_receipt_pays_owner ... ok
test tests::daily_cap_blocks_then_resets_next_day ... ok
test tests::withdrawal_success_callbacks_emit_events ... ok
test tests::withdrawal_failure_callbacks_restore_balances ... ok
test tests::revoked_expired_scope_and_credit_paths ... ok
test tests::recent_receipts_ring_is_capped_and_newest_first ... ok
test result: ok. 13 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 1.49s
== crypto: build, typecheck, unit + vector tests ==
$ tsc -p tsconfig.json
$ vitest run
 RUN  v5.1.0 /home/radon/HACKS/Mnemos/packages/crypto
 Test Files  1 passed (1)
      Tests  21 passed (21)
   Start at  12:49:43
   Duration  5.25s (tests 88%, import 12%)
== broker: ruff, mypy, unit tests ==
All checks passed!
57 files already formatted
Success: no issues found in 37 source files
.....................................................................    [100%]
69 passed, 54 deselected in 0.69s
== mcp: typecheck, lint, tests ==
$ tsc -p tsconfig.json --noEmit
$ eslint .
$ vitest run
 RUN  v5.1.0 /home/radon/HACKS/Mnemos/apps/mcp
 Test Files  5 passed (5)
      Tests  32 passed (32)
   Start at  12:49:16
   Duration  1.23s (tests 75%, import 22%, other 3%)
== web: typecheck, lint, tests ==
No projects matched the filters in "/home/radon/HACKS/Mnemos"

All checks passed.
```

The web section is a no-op until the web app lands in Phase 6.


## Phase 2 — contract

```text
$ cd contracts/mnemos && cargo test --lib
running 13 tests
test tests::refund_restores_credit_and_cap ... ok
test tests::withdrawal_success_callbacks_emit_events ... ok
test tests::withdrawal_failure_callbacks_restore_balances ... ok
test tests::revoked_expired_scope_and_credit_paths ... ok
test tests::recent_receipts_ring_is_capped_and_newest_first ... ok

test result: ok. 13 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 1.60s

$ cd contracts/mnemos && cargo test --test integration
running 2 tests
test pause_and_withdrawals ... ok
test full_lifecycle_and_negative_paths ... ok

test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 36.71s

$ cd contracts/mnemos && cargo clippy --all-targets -- -D warnings
    Checking mnemos-contract v0.1.0 (/home/radon/HACKS/Mnemos/contracts/mnemos)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 15.50s

$ cd contracts/mnemos && cargo near build non-reproducible-wasm
     -                  Size: 252.7 KB (252650 bytes)
     - SHA-256 checksum hex : aa18000844e238db3c74f9cd1a384e0abc8caac30e73f46ea0b446035082f4c5
     - SHA-256 checksum bs58: CSyXzu8UtBYNtphRbZ6M4o2wkYLQgEAgM3LjhccYPstp
     Finished cargo near build in 0s

$ sha256sum target/near/mnemos_contract.wasm
aa18000844e238db3c74f9cd1a384e0abc8caac30e73f46ea0b446035082f4c5  target/near/mnemos_contract.wasm
```

Testnet state, read back with independent view calls:

```text
get_config  -> owner mnemos-owner-76badc8e.testnet, paused false,
               request_ttl_ns 600000000000, day_ns 86400000000000
get_broker  -> broker mnemos-broker-76badc8e.testnet,
               fingerprint f15d7141fd619dd65cc7fac29cb5a3a11d642aaa47f6a00f757bfedf9e6eb0a4
credit_of   -> 5000000000000000000000000
```

## Phase 3 — crypto interop

```text
$ pnpm --filter @mnemos/crypto test
$ vitest run

 RUN  v5.1.0 /home/radon/HACKS/Mnemos/packages/crypto

 Test Files  1 passed (1)
      Tests  21 passed (21)
   Start at  12:38:44
   Duration  5.08s (tests 88%, import 12%)

$ cd apps/broker && uv run pytest -q tests/test_crypto.py
10 passed in 0.56s
```

Both languages re-encrypt the three committed vectors byte for byte, and each
language decrypts the other's output with the owner passphrase and with the
broker X25519 key. Tamper tests reject modified ciphertext, scope, owner, item
id, passphrase, salt, wrapped DEKs and a mismatched content hash.

## Phase 4 — broker

```text
$ cd apps/broker && uv run ruff check src tests
All checks passed!

$ cd apps/broker && uv run ruff format --check src tests
57 files already formatted

$ cd apps/broker && uv run mypy --strict src
Success: no issues found in 37 source files

$ cd apps/broker && uv run pytest -q
68 passed, 54 deselected in 0.70s

$ cd apps/broker && uv run pytest -q -m integration
54 passed, 68 deselected in 6.45s
```

The 68 unit tests cover the envelope filter (12-word runs, base64 and hex
encodings, Unicode folding), prompt construction and delimiter escaping,
ranking and the context budget, session signing and expiry, NEP-413 and agent
signature verification, request and grant parsing, contract error mapping, the
token bucket, the activity publisher and the request schemas.

The 54 integration tests run against a real Postgres 16 database and cover the
owner challenge/verify/replay/expiry path, key ownership checks, the session
cookie, vault create/list/paginate/delete/salt rules, vault isolation between
owners, the happy-path ask with a settled receipt, replay, concurrent double
spend, scope denial, revoked and expired grants, paused contract, missing
memory, inference failure, verification failure, output filter withholding,
receipt failure, rate limiting, the sweeper and the merged activity feed.

### Live NEAR AI Cloud answer, E2EE with TEE attestation

```text
$ uv run --project apps/broker python scripts/verify-nearai.py
{
  "answer": "Your flight is on 14 March at 09:15.",
  "attestation": {
    "advisory_ids": [],
    "deployment": {
      "app_compose_sha256": "448683dd83e50727b9c5f6cdc84bd9d93fcf2c888001a85b1ba32f76b3612e3e",
      "compose_hash": "448683dd83e50727b9c5f6cdc84bd9d93fcf2c888001a85b1ba32f76b3612e3e",
      "compose_manager_verified": true,
      "os_image_hash": "91fd5d69ccee3e5ea4f2aeb8c9b632c4358c4ecfc29ba1aa6fb1e402af209829"
    },
    "deployment_provenance": "not_checked",
    "gpu_evidence": "verified",
    "model_attestations": 1,
    "signature_kind": "provider_tee",
    "signer": {
      "signing_address": "236f5a6b91dd47dc3b7b36e43d4eb531a042ffb8f8fbf3a1555b78cef4fdda4c",
      "signing_algo": "ed25519"
    },
    "tcb_status": "UpToDate",
    "verified_at": "2026-11-11T07:07:00+00:00"
  },
  "chat_id": "chatcmpl-0787e883-2a13-4acb-880e-d2487cc394c7",
  "e2ee": true,
  "model": "deepseek-ai/DeepSeek-V4.1-Flash-1017",
  "ok": true,
  "request_sha256": "2ddd92190c7213fa491d7bedcf81c5124236cc7f340ecb0a82ba0bb11d17f0ec",
  "response_sha256": "f917824dead57c24d49f4feb7492fe956644d0b2384ff9874877524e4b77769f",
  "signature_kind": "provider_tee",
  "signing_address": "236f5a6b91dd47dc3b7b36e43d4eb531a042ffb8f8fbf3a1555b78cef4fdda4c",
  "signing_algo": "ed25519"
}
```

The broker never uses an answer before `verify_response` succeeds, and it has
no unverified fallback path.

## Phase 5 — MCP server

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

