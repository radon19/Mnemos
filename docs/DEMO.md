# Mnemos laptop demo

## Start

```bash
cd Mnemos
make demo-ready
```

Open **http://localhost:3000/exchange**. Use `localhost` consistently: the
owner cookie is shared by the web app and broker on that host. The running
main demonstration uses testnet and needs internet access and NEAR AI credit.
The separate Agent API wallet uses mainnet USDC and remains unfunded by choice.
The command reuses `.env` and `.secrets/accounts.json`, enables the local
signers, starts the stack and checks the deployment. It does not delete
notes, reset grants, reset balances or redeploy the contract.

## The story to tell

“AI agents need useful knowledge, but handing over an entire private notebook
is too much access. Mnemos lets its owner sell a bounded answer instead.
This Lisbon specialist and this buying agent have separate NEAR accounts.”

1. **Start local owner session.** Both real accounts are controlled from this
   laptop for the demonstration. No browser wallet is required.
2. **Encrypt demo knowledge.** Expand the dossier and private note to show
   their labeled fictional sample content. The browser encrypts before
   upload. The button becomes “Sample knowledge sealed” on repeat runs.
3. **Grant expertise access.** Terms: 0.001 testnet NEAR per answer, eight
   reads per UTC day, 24-hour expiry, 256 answer tokens. The private scope is
   excluded. “Renew expertise access” reopens a revoked grant. A matching
   active grant keeps its daily usage.
4. **Ask for 0.001 NEAR.** A real read is created on NEAR; the broker decrypts
   the granted scope, performs verified E2EE inference, filters the result
   and settles the receipt. Expect roughly 20–60 seconds.
5. **Inspect evidence.** Show the answer, receipt hash, settlement link,
   signature kind, signing address, TCB and deployment fields. Balances come
   from the chain. The receipt itself does not prove inference correctness.
6. **Try private scope.** `E_SCOPE_DENIED` comes from the deployed contract,
   before decryption. No read fee is charged; failed transactions may still
   consume testnet gas.
7. **Revoke access**, confirm the named agent, then **Try the same question**.
   The contract returns `E_GRANT_REVOKED`. Earlier answers and receipts stay
   visible. “The owner can stop future access without asking the agent.”

Close with: “NEAR enforces the terms and settles payment. NEAR AI protects
private inference. MCP lets existing agents use the same protocol. The
owner-run broker is an explicit trust boundary.”

## Agent API and judging checks

Below the testnet receipt, **Buy through NEAR Intents** reads a real Agent API
wallet and its owner-signed policy. It shows **Funding needed**; the 0.01 USDC
purchase button is disabled. These funds are separate from testnet credit.
No mainnet purchase/refund is represented as completed.

`make agent-api-check` issues real execution requests to demonstrate destination,
per-transaction limit and revoked-grant refusals. The separate zero-budget probe
hits balance validation first, so it is explicitly not counted as a verified
USD-budget refusal. `make judging-check` also verifies a current real model
answer and rejects a real attestation under a different nonce. See
[NEAR_INTEGRATION.md](NEAR_INTEGRATION.md) for the code map and exact remaining limits.

The stricter model is `Qwen/Qwen3.8-27B`. Each inference uses fresh attestation;
only a provider signature with one matching verified report is accepted.
The recorder includes the actual unfunded Agent wallet after revocation.

For an unresolved USDC read, refresh wallet status and keep the same purchase
ID. **Recover or refund by ID** does not need the original question and never
starts a new purchase. Unknown or pending settlement is not a successful answer.

## Record automatically

```bash
make doctor
make record-demo
```

The recorder uses the actual UI and services, without intercepting requests.
It asserts a paid answer, scope denial and revoked denial, saves public
testnet evidence and screenshots, and fails on browser errors. Outputs:
`artifacts/demo/mnemos-demo.webm`, `evidence.json`, desktop, phone and dark
screenshots. Generated files are gitignored; curated evidence is recorded in
`docs/VERIFICATION.md`. The raw recording is silent; use the narration above. The delivered
`artifacts/demo/mnemos-demo-captioned.mp4` includes concise captions, and
`mnemos-demo.srt` is available for editing.

Convert for sharing with ffmpeg:

```bash
ffmpeg -y -i artifacts/demo/mnemos-demo.webm -c:v libx264 -preset fast -crf 22 -pix_fmt yuv420p -movflags +faststart artifacts/demo/mnemos-demo.mp4
```

## Recovery

- **Unavailable services/RPC:** `make doctor`, then `docker compose logs
  --tail=60 web broker`. Restore connectivity and Refresh status.
- **Expired session:** sign out and Start local owner session again.
- **Revoked grant:** Renew expertise access. It explicitly replaces this
  demo agent's terms; other agents' grants are unaffected.
- **Daily cap:** resets at UTC midnight. Do not silently replace the grant
  to disguise the limit.
- **Withheld answer:** the read fee is refunded. Inspect the failure rather
  than presenting fabricated evidence.
- **Lost connection after submission:** check Activity before repeating;
  the transaction may already have settled.
- **Read sample notes in Vault:** public sample passphrase
  `mnemos-demo-expertise`, for these samples only. Existing notes retain
  their original passphrases. Never use the sample passphrase for real data.

## Trust today, future scope tomorrow

This is an owner-operated prototype, not a hosted marketplace. The broker
can decrypt items wrapped for it and must be trusted to enforce scope.
Repeated queries, paraphrases and translations can reveal facts; the lexical
filter is not complete data-loss prevention. Revocation cannot retract past
answers. Receipts prove broker settlement, not independent execution.
Testnet earnings are not real revenue. The [roadmap](ROADMAP.md) turns these
boundaries into concrete milestones: attested broker execution, disclosure-aware
policies, funded commerce and independent expertise offers.

The slow sandbox next-day test stays opt-in (around twelve minutes); UTC cap
rollover is covered directly by unit tests. Neither recording nor startup
posts anything or submits the entry. Review `docs/SUBMISSION.md`, publish
your repository and demo, and submit those links yourself.
