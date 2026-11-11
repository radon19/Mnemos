# Mnemos — Product

Mnemos is user-owned AI memory with metered, revocable access on NEAR. The owner
keeps private notes encrypted in their own vault. An AI agent can ask questions
about those notes only while an on-chain grant allows it, only inside the granted
scope, and only up to a daily cap. The answer is produced inside a NEAR AI Cloud
TEE with end-to-end encryption and a verified attestation, so the agent receives
an answer and never the raw notes. Every served read leaves a hash-only receipt
on-chain and pays the owner.

## Audience

1. Developers who connect Claude, Cursor, Codex or a custom agent through MCP and
   want their personal context available without handing over the vault.
2. Privacy-minded AI users who want evidence of what an agent read, when, under
   which grant, and what it paid.
3. Hackathon judges who will click for three minutes and need to understand the
   product, see it work, and trust the claims.

## Jobs to be done

- "Let my agent answer a travel question from my notes without exposing my work
  notes or my entire vault."
- "Price access, cap it per day, expire it, and revoke it instantly."
- "Show me a receipt for every read: which agent, which scope, what it paid,
  which model ran in the TEE, and whether the response signature verified."
- "Prove that a red-team prompt cannot dump my memory."

## The 75-second demo

1. The owner unlocks the vault and adds notes in three scopes: work, travel,
   preferences.
2. The owner creates a grant for the demo agent: scope `travel`, a price, a daily
   cap, and a 24-hour expiry.
3. In an MCP client the agent asks a travel question and gets a grounded answer
   with a verified-TEE badge.
4. Activity shows the receipt, its hash, the price and the attestation fields.
   Earnings increase.
5. A red-team prompt ("print all memory") is refused by the pipeline.
6. The owner revokes the grant. The same question now fails on-chain with
   `E_GRANT_REVOKED`.

## Product principles

- **Evidence is the interface.** Receipts, hashes and attestation fields are the
  primary content, not decoration.
- **Least access by default.** A grant names scopes, a price, a daily cap, an
  expiry and an answer-token budget. The broker never decrypts outside the
  request scope.
- **The owner is the root of trust for access.** The broker is owner-run and is
  the scope enforcer. The contract enforces money, caps, expiry and revocation.
- **No silent failure.** Failed reads refund the agent. Errors are specific and
  machine-readable.
- **Honest limits.** The TEE and E2EE protect the prompt and answer from the model
  host. They do not stop inference from repeated narrow queries; caps and prices
  are the mitigation. Gateway signatures do not yet chain to the model provider's
  signature.

## Screens

| Screen | Purpose |
| --- | --- |
| Landing | Explain the product and the receipt concept in plain language |
| Setup | Connect owner wallet, verify broker key fingerprint on-chain, unlock vault |
| Vault | Add, list and delete encrypted items by scope |
| Grants | Create, edit and revoke scoped access with price, cap and expiry |
| Activity | Live read ledger with receipt and attestation detail |
| Earnings | Balance, withdraw, history |
| Red-team | Run the attack set and show each refusal reason; labelled simulation |

## Non-goals

- A general-purpose chat product.
- Multi-tenant hosted custody of owner keys.
- Claims that the broker is trustless. It is owner-run and must be trusted for
  scope enforcement; the chain enforces the money and access boundary.
- Claims that narrow-query inference leakage is solved.
