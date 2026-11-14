# Engineering decisions

These decisions describe the shipped prototype and the tradeoffs that shape its
[next milestones](ROADMAP.md). They are intentionally separate from feature
claims and test results.

## 1. Sell an authorized answer

The useful unit is a grounded answer under explicit access terms, not a copy of
the source vault. This makes scope, answer length, price, read caps, expiry and
revocation part of the transaction. The agent-facing MCP tools expose the answer
service and its terms; owner vault management remains a separate authenticated
surface.

## 2. Keep knowledge permission and spending policy separate

The expert decides which knowledge can be used. The buyer decides what its wallet
may spend. Mnemos' contract retains knowledge entitlements, testnet escrow,
settlement commitments and refunds. The separate USDC offer uses the official
Agent API for owner-signed wallet policy, runtime grants and Intents transfers.

The rails have independent balances, counters and evidence. A mainnet USDC
purchase never pretends to debit testnet credit or create a testnet receipt.
Native Agent API contract calls are not used to claim generic USD-budget control,
because those calls have different enforcement boundaries.

## 3. Keep the broker owner-operated

The owner chooses the broker and its encryption key. This makes the prototype
reproducible on a laptop while keeping custody and deployment control explicit.
The broker still processes plaintext and must be trusted for off-chain scope
selection. Attested broker execution with sealed-key binding is a future
milestone, not a current security property.

## 4. Require model evidence, not a generic verified badge

A fresh SDK client with zero attestation cache is created for each inference.
The pinned SDK verifies nonce/quote/deployment evidence before sending the E2EE
prompt and verifies the response against retained wire bytes. Mnemos additionally
requires `provider_tee` and one matching verified model report.

`Qwen/Qwen3.8-27B` passed this policy in the live check. The prior DeepSeek model
returned two different measured deployments sharing a signer; the stricter
policy rejects that ambiguity. The Qwen completion disables its default hidden thinking so the bounded output
budget produces a final answer; the token cap and verification policy stay intact.
Availability is deliberately secondary to
releasing an unverified response. Application receipt hashes are labeled
separately from the SDK's exact wire-signature hashes.

## 5. Persist money state before the next external effect

A per-read database advisory lock serializes a USDC purchase. Separate commits
persist accepted operation IDs and payment/refund transitions before polling or
initiating the next effect. Stable external idempotency keys preserve purchase
identity across retries.

Independent review found three recovery defects that were reproduced and fixed:
a crash after external refund, accepted payment recovery after grant rotation,
and refund recovery without the original question or old session secret.
Their regression tests use deterministic HTTP fixtures with real Postgres.
They are not represented as funded mainnet evidence.

Unfinished purchases are discoverable separately from recent completed receipts.
Plaintext answers are not retained for replay after delivery.

## 6. Separate runtime keys from account management

The local reader has a function-call key for only `request_read` and
`expire_request` on one contract. The recovery/funding key stays separate.
The default 30 Tgas reservation fits the configured limited allowance; doctor
checks both the current gas price and the protocol's upfront purchase-price
floor. A positive allowance alone is not sufficient evidence that a key can
submit the configured transaction.

## 7. Activate mainnet explicitly

The user chose to keep the Agent API wallets unfunded. Real provisioning and
three policy refusals are verified. A successful mainnet sale, refund and
USD-budget refusal are not claimed as live-verified. The zero-budget probe
currently reaches balance validation first.

This keeps the demonstration's real testnet payment and its mainnet activation
milestone easy to distinguish. The UI shows Funding needed and disables new
mainnet purchases while the wallet is empty.

## 8. Preserve the product identity and review workflow

The existing violet/white visual theme, fonts, light/dark behavior and shared
components remain the design system. The current monogram is shared by the
navigation and browser icon. [DESIGN.md](../DESIGN.md) and
[UX-CONTRACT.md](../UX-CONTRACT.md) retain the design and interaction contracts.

The user requested no commits. Changes remain in the working tree for their
review; no repository publishing or hackathon submission is automated here.

## Further hardening

The offline setup helper verifies signing standard and owner identity, then
trusts the official API's generated EIP-712 message. Independently validating its
domain and operation contents would reduce that service trust before a wider
rollout. The runtime does not hold the setup owner's signing key.

[Architecture →](ARCHITECTURE.md) · [NEAR integration →](NEAR_INTEGRATION.md)
