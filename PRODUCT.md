# Mnemos product context

**Private expertise. Paid answers. Access you control.**

Mnemos is an owner-operated knowledge exchange for AI agents. An expert stores
browser-encrypted notes, authorizes a named agent to use a knowledge scope, and
sets the price, read cap, expiry and answer budget. The agent buys a grounded
answer with separate inference and settlement evidence.

## The demonstration

A Lisbon specialist offers an expertise dossier while keeping private business
notes outside the grant. A separate agent buys a useful travel answer through
MCP. The UI shows the real testnet receipt and verified model evidence, refuses
an ungranted private scope, then refuses a new read after revocation.

The Agent API / Intents offer is a separate mainnet USDC path with owner-signed
wallet policy and recoverable settlement. Its wallets are intentionally
unfunded; the UI disables new purchases and does not invent a payment.

## Intended users

| User | Job |
| --- | --- |
| Expert or knowledge owner | Make selected knowledge useful while controlling access and terms. |
| Agent developer | Obtain scoped context through a familiar MCP interface without receiving a vault API. |
| Reviewer or operator | Reproduce the flow and inspect what was authorized, verified and settled. |

## Product principles

- **Evidence is part of the product.** Price, scope, receipt and verification
  fields remain inspectable; they do not collapse into one vague trust badge.
- **Knowledge authority and spending authority are distinct.** The expert
  controls knowledge access. The buyer's wallet policy controls spending.
- **Owner-operated by design.** The broker is chosen and trusted by the owner;
  its off-chain plaintext processing is explicit.
- **Failures are visible.** Pending settlement and refunds are not reported as
  success. Retries preserve the purchase identity.
- **Useful answers disclose facts.** Scope, caps and answer policies bound the
  interaction. The output filter is not a complete non-disclosure proof.
- **Demonstrated and planned are separate.** Mainnet activation and stronger
  broker isolation have specific roadmap acceptance evidence.

## Application surfaces

| Surface | Purpose |
| --- | --- |
| Home | Explain the exchange and show actual testnet figures. |
| Exchange | Guide the paid-answer, refusal and revocation story; inspect the separate Agent wallet. |
| Setup | Authenticate the owner and verify deployment/broker binding. |
| Vault | Encrypt, inspect and remove owner notes by scope. |
| Grants | Manage named-agent knowledge terms. |
| Activity | Inspect read history, settlement and inference evidence. |
| Earnings | Inspect testnet earnings and owner-wallet withdrawal. |
| Red-team | Run real-model adversarial checks and report observed/residual outcomes. |
| Docs | Explain operation, architecture and trust in the application. |

The visual and behavioral sources of truth are [DESIGN.md](DESIGN.md) and
[UX-CONTRACT.md](UX-CONTRACT.md). Public documentation starts at [README.md](README.md).
