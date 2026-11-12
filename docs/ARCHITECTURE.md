# Architecture

## The components

| Component | Language | Responsibility |
| --- | --- | --- |
| Mnemos contract | Rust, `near-sdk` 5.30 | Grants, caps, expiry, credit, receipts, refunds. It holds money and the access boundary. |
| Broker | Python 3.12, FastAPI | The scope enforcer. Decrypts one scope, calls the model, filters the answer, settles the receipt. |
| MCP server | TypeScript, `@modelcontextprotocol/sdk` 1.32 | The agent side: `ask_memory`, `list_grants`, `check_credit`. |
| Web app | TypeScript, Next.js 16 | The owner side: setup, vault, grants, activity, earnings, red-team. |
| Crypto | TypeScript and Python | The same envelope format, verified byte for byte against shared vectors. |

## The read path

The order is the design. Nothing is decrypted before the money has moved.

1. **The agent creates the request.** `request_read(owner, scope, q_hash)` on
   the contract. The contract checks the grant, the scope, the daily cap and
   the agent's prepaid credit, takes the price, and creates the request in
   state `Approved`. A request that is never served expires after ten minutes
   and the credit comes back.
2. **The agent asks the broker.** It signs
   `mnemos:v1:ask|{req_id}|{sha256(question)}|{nonce_hex}|{recipient}` with
   its key and posts it to `/v1/ask`. The broker verifies the signature, then
   verifies through `view_access_key` that the signing key belongs to the
   agent account named in the request.
3. **The broker claims the request.** The insert into `read_requests` uses
   the request id as the primary key, so two concurrent calls for the same
   request produce exactly one served read.
4. **The broker decrypts one scope.** Items are selected by owner and scope,
   decrypted with the broker's X25519 key, ranked by lexical relevance and
   recency, and capped to a token budget. Plaintext never reaches a log.
5. **The model answers.** The completion runs with `e2ee=True` against
   `deepseek-ai/DeepSeek-V4.1-Flash-1017`. The broker calls
   `verify_response` and refuses to use an answer that does not verify.
6. **The output filter runs.** Any answer sharing a contiguous run of twelve
   or more words with a decrypted item is rejected, including runs hidden in
   base64 or hex. The broker retries once with a stricter prompt and refunds
   if the second attempt still leaks.
7. **The receipt is settled.** `receipt_hash = sha256(req_id|chat_id|
   sha256(request_bytes)|sha256(response_bytes)|signing_address)` is written
   with `record_receipt`. The chain stores the hash, the price and the scope,
   never the content.

## Storage

The broker's database holds ciphertext and evidence, never plaintext.

| Table | Holds |
| --- | --- |
| `vault_items` | Ciphertext, nonce, both wrapped DEKs, the content hash, the scope. |
| `owner_accounts` | The owner's account id and the PBKDF2 salt. |
| `read_requests` | The request id, the q_hash, the price, the status, the receipt and refund transaction hashes, the attestation summary, the latency and the error code. |
| `auth_challenges` | The exact NEP-413 message, the nonce, the expiry and the single-use marker. |
| `audit_events` | Identifiers and error codes for sign-in and settlement failures. |

Prices are `numeric(78, 0)`, because a NEAR price is a u128 amount of
yoctoNEAR and does not fit in a signed 64-bit integer.

Nothing grows without bound either. A retention job removes expired sign-in
challenges after an hour, audit events after a month, deleted vault items after
a month and read requests after a quarter. The chain keeps the receipt ring, so
the history of a read never disappears, only the broker's copy of the
bookkeeping.

## The views

`get_grant`, `get_request`, `credit_of`, `earnings_of`, `get_broker` and
`recent_receipts` answer single questions. `grants_by_owner` answers the one
the owner interface could not do without: it lists every grant an owner gave,
so the Grants screen shows the same list in every browser and on chain.

## The envelope

```text
item ciphertext        ciphertext || 16-byte tag, nonce stored separately
owner-wrapped DEK      12-byte nonce || ciphertext || tag
broker-wrapped DEK     32-byte ephemeral public || 12-byte nonce || ciphertext || tag
```

The item is sealed with AES-256-GCM under a random per-item data key. The
owner wraps that key with a key derived from their passphrase
(PBKDF2-HMAC-SHA256, 600000 iterations, a 16-byte salt per owner). The broker
wraps the same key with HKDF-SHA256 over an X25519 exchange with the broker's
public key. The AAD strings bind every wrap to the owner, the scope and the
item id, so an envelope cannot be moved between scopes or owners.

The TypeScript and Python implementations are pinned to the same byte layout
by `packages/crypto-vectors/vectors.json`. Both re-encrypt every vector byte
for byte and decrypt the other's output, so the browser and the broker always
agree.

## API surface

| Endpoint | Who | What |
| --- | --- | --- |
| `POST /v1/auth/challenge` | owner | A single-use NEP-413 challenge, five minute TTL. |
| `POST /v1/auth/verify` | owner | Verifies the signature, checks key ownership, sets the session cookie. |
| `GET /v1/broker/pubkey` | anyone | The broker's public key and its fingerprint. |
| `POST /v1/vault/items` | owner | Stores an envelope the broker could open. |
| `GET /v1/vault/items` | owner | Lists the owner's items. |
| `GET /v1/vault/salt` | owner | The owner's KDF salt. |
| `DELETE /v1/vault/items/{id}` | owner | Removes an item. |
| `POST /v1/ask` | agent | The signed read request. |
| `GET /v1/activity` | owner | The merged broker and chain read ledger. |
| `GET /v1/activity/stream` | owner | The same ledger as server-sent events. |
| `POST /v1/redteam/run` | owner | Starts the attack set as a background job and returns its id. |
| `GET /v1/redteam/run/{job_id}` | owner | The state of a red-team job and, when it is done, the report. |
| `GET /healthz`, `GET /readyz` | anyone | Liveness and readiness. |

Every error carries a stable code (`E_GRANT_REVOKED`, `E_SCOPE_DENIED`,
`E_OUTPUT_FILTER`, …) and a request id. The MCP tools translate those codes
into a sentence with the next action.

## Deployment

```text
docker compose up -d --build
```

brings up Postgres 16, the broker and the web app. The broker container runs
`alembic upgrade head` before it starts serving, and both services have
health checks. The contract is separate: it is deployed to testnet with
`./scripts/deploy-testnet.sh`, which is idempotent and prints the contract
id.

Rate limiting and the activity stream are single-instance by design: both
live in the broker process. A deployment with more than one replica needs a
shared limiter and a shared event bus; this is recorded as a limitation in
`docs/SECURITY.md`.
