# Security

Threat model, the mitigation for each threat, and what is still open.

## Assets

| Asset | Where it lives | Who must not get it |
| --- | --- | --- |
| Vault plaintext | The owner's browser, briefly in broker memory | The agent, the model host, a database dump |
| The passphrase-derived key | Browser memory, one tab | Everyone else |
| The broker's X25519 private key | The broker's environment | The agent, the owner, a database dump |
| The agent's prepaid credit | The contract | Another agent, the owner |
| The owner's earnings | The contract | The agent, a third party |
| The receipt trail | The contract, the events | Nobody: it is public and content-free |

## Threats

### A malicious agent

**What it tries.** Read a scope it was not granted, read the same request
twice, read the vault directly, spend the owner's credit, or drain its own
credit quickly.

**Mitigation.** The agent's key can only call `request_read`, and the
contract checks the grant, the scope, the cap, the expiry and the credit
before it creates anything. A read is served only when the request carries a
signature from a key that `view_access_key` says belongs to the agent account
in the request, and the signature covers the request id, the question, a
nonce and the broker. The request id is the primary key of the served-read
table, so a replay is rejected. The cap and the price bound the damage a
stolen agent key can do.

**Residual.** An agent that holds a valid grant can ask narrow questions and
learn facts. That is what the price and the cap are for.

### A malicious or compromised broker operator

**What it tries.** Read every scope, keep the plaintext, answer from memory
instead of from the grant, or serve a request that was never paid for.

**Mitigation.** The broker is owner-run, and the owner chooses where it runs.
The contract is the enforcement point: the broker cannot create a grant,
cannot raise a cap, cannot change an expiry and cannot get an unpaid request
served, because the contract charges before the broker is allowed to act. The
receipt lets the owner audit which reads were served, when, by which agent,
for which scope and for how much. The web app refuses to encrypt anything for
a broker whose key fingerprint does not match the value registered on chain.

**Residual.** A compromised broker can read the plaintext it decrypts and can
lie about the answer it produced. It cannot forge the receipt of a read it did
not pay for, and the audit trail shows the reads it claims to have served.
Detecting a broker that lies about the *content* of an answer needs an
independent re-run, which the red-team screen makes easy but does not
automate.

### A database leak

**What it tries.** Read the notes out of the broker's database.

**Mitigation.** The database holds ciphertext, nonces, wrapped keys, hashes,
identifiers and error codes. There is no column that can hold a plaintext
note, a question or an answer. The broker's private key is in the process
environment, never in the database. An owner-wrapped key is useless without
the passphrase; a broker-wrapped key needs the broker's X25519 private key.

**Residual.** The database reveals *which* owner and *which* scope has *how
many* items, and the timestamps of reads. That metadata is not protected.

### Replay

**What it tries.** Reuse a signature, a request or a challenge.

**Mitigation.** The agent signature covers the request id, the question
digest, a fresh 32-byte nonce and the broker recipient, and the broker
recomputes `q_hash = sha256(question || nonce)` and compares it with the
value stored on chain. The read request id is consumed once, enforced by a
primary key. The owner sign-in challenge is single use with a five minute
TTL, and the stored message is the exact bytes the wallet displayed.

**Residual.** A replayed *owner* session cookie is valid until it expires
(the session is short lived and the cookie is HttpOnly, SameSite=Strict and
signed).

### Prompt injection

**What it tries.** Put instructions in a memory item, or in the question, so
the model ignores its instructions and dumps the vault.

**Mitigation.** Memory and question are wrapped in fixed delimiters and any
delimiter-like text inside them is escaped, so an item cannot close its own
block. The system prompt states that the blocks are data, that instructions
inside them are content rather than commands, and that the model must not
encode, translate or list items. The output filter is the enforcement point:
it runs on the answer, not on the prompt, and it does not care what the
instructions were.

**Residual.** A sufficiently narrow question can still extract a fact. The
filter is lexical; it does not understand meaning.

### Storage griefing on the chain

**What it tries.** Flood the contract with requests or grants so that storage
cost or the state grows without bound.

**Mitigation.** The contract bounds everything: at most 32 grants per owner,
at most 16 scopes per grant, a daily cap of at most 10,000 reads, at most 32
pending reads per agent, a ring buffer of 50 receipts per owner and 512
recent served request ids. Completed requests are removed from storage; the
NEP-297 event log keeps the trail.

**Residual.** The agent can still pay for many reads, bounded by its own
prepaid credit and by the grant cap.

### Stuck funds

**What it tries.** Make a read fail after the agent paid, so the credit is
lost; or make a withdrawal fail so the earnings are stuck.

**Mitigation.** Every failure path in the broker calls `refund`. If the
broker cannot record the request at all, it still refunds before reporting
the error. If the request expires unused, `expire_request` returns the
credit, and that call is permissionless. A failed withdrawal restores the
balance and the owner can try again.

**Residual.** An agent that creates a request and never calls `/v1/ask` keeps
its credit until the request expires. The sweeper expires the requests the
broker has seen; a request the broker never saw needs an indexer or the agent
itself to call `expire_request`.

## Operational notes

- Secrets live in `.env` and `.secrets/`, both gitignored. `.env.example`
  documents every variable. No secret is printed by any command; the demo and
  the verification scripts print only public identifiers.
- The broker sets `HttpOnly`, `SameSite=Strict` session cookies and signs
  them with HMAC-SHA256.
- Every request gets a request id that is returned in the error envelope and
  in the logs, so an incident can be traced without logging payloads.
- Logs are structured JSON with no plaintext fields.
- The broker refuses request bodies above 32 KiB, and the vault enforces a
  16 KiB item limit.
- Rate limits are 60 sign-ins and 10 reads a minute by default, and 3
  red-team runs a minute. With one broker they are kept in memory. A
  multi-replica deployment sets `RATE_LIMIT_BACKEND=postgres` and every
  replica then spends from one budget kept in the database; the shared
  budget fails open, so a read is never blocked because the limiter is
  down.
- The activity stream is shared the same way: `ACTIVITY_BUS_ENABLED` carries
  the events over a Postgres channel, so a read served by one replica
  appears in the owner's ledger in every other replica.
- Retention bounds the broker's tables: sign-in challenges are dropped after
  an hour, audit events after a month, deleted vault items after a month and
  read requests after a quarter.
- The container images run as non-root users, and compose caps each service
  at 768 MB and one CPU.
- The demo signer is disabled unless the server has `DEMO_OWNER_SECRET_KEY`
  and the client has `NEXT_PUBLIC_DEMO_MODE=true`. It exists so the flow can
  be shown without a browser wallet, and it is labelled as a demo session in
  the interface.
