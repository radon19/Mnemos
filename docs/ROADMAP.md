# Roadmap

## From a controlled knowledge exchange to an agent-accessible expertise economy

Mnemos starts with a concrete transaction: an expert authorizes a bounded
question, an agent pays, and the answer arrives with evidence. The next phase
extends that transaction without weakening the owner's control.

This roadmap distinguishes the shipped prototype from future capabilities.
Planned milestones are not represented as completed integrations.

## The foundation already built

- Browser-side envelope encryption with owner and broker key wraps.
- Named-agent knowledge grants with scope, price, read cap, expiry and revocation.
- Real NEAR testnet escrow, settlement receipts and failed-read refunds.
- NEAR AI Cloud E2EE inference with fresh verified preflight evidence and a
  required model-serving TEE signature.
- Restricted local agent keys and owner-signed Agent API wallet policies.
- Payment idempotency, durable operation identifiers, and recovery that survives
  a crash, grant rotation or loss of the original question.
- A working owner dashboard, MCP tools and a repeatable laptop demonstration.

## 1. Mainnet activation: turn verified controls into funded commerce

**Why this sequence matters.** The testnet flow validates access and settlement
without presenting rehearsal tokens as revenue. The separate Agent API wallets
make the mainnet spending policy inspectable before they receive funds.

**Next scope**

- Fund the existing buyer wallet through the implemented 1Click deposit helper.
- Execute a small USDC expertise purchase and compare both sides' balances.
- Exercise an actual failed-answer refund and preserve its execution evidence.
- Verify a USD-budget refusal with a funded wallet so balance validation does
  not stop the request first.

**Exit evidence:** a matched successful payment, a verified model answer, a
confirmed refund, and budget/destination refusal records from the funded path.

**Current status:** wallet provisioning and three real policy refusals are
verified. Successful mainnet sale/refund and USD-budget rejection remain
unverified because the wallets are intentionally unfunded.

## 2. Attested broker execution: reduce trust in the operator

**The starting choice.** An owner-run broker keeps deployment and encryption-key
control with the knowledge owner. Today it sees the plaintext needed to answer
and must be trusted to enforce off-chain scope selection.

**Next scope**

- Run the scope selection, decryption and answer policy inside an attested broker.
- Seal decryption keys to an approved measured deployment.
- Bind the broker's measurement and policy version to the evidence returned for
  a paid read.
- Add key rotation, migration and recovery procedures before broader hosting.

**Exit evidence:** a client can verify the broker deployment and its key binding,
not only the model-hosting environment.

This would extend the existing trust boundary; it is not a property claimed by
the current owner-operated broker.

## 3. Disclosure-aware knowledge policies: preserve usefulness over many queries

**The starting choice.** Mnemos already enforces scoped access and limits long
verbatim reproduction, including supported encoded forms. A useful authorized
answer still communicates facts, and repeated or translated answers can reveal
more than a lexical filter can measure.

**Next scope**

- Track cumulative query and disclosure budgets within each knowledge offer.
- Add topic-specific rules and more granular expert-approved answer policies.
- Expand adversarial evaluations to paraphrase, translation and coordinated
  multi-agent extraction.
- Show owners evidence of policy coverage alongside observed residual behavior.

**Exit evidence:** repeatable evaluations demonstrate which attacks a policy
handles and where it still permits disclosure. No blanket “leak-proof” claim.

## 4. Client-verifiable commerce: make the evidence portable

**The starting choice.** The current application checks Agent API execution
status against the exact buyer, asset, amount, recipient and purchase reference.
It retains the resulting intent identifier and separates it from model evidence.

**Next scope**

- Verify the Agent API's published execution/transparency evidence in the client.
- Export a portable evidence bundle for each completed purchase.
- Add payment reconciliation tools for provider outages and operator handover.
- Version receipt formats and verification policies for long-lived integrations.

**Exit evidence:** another verifier can independently inspect the supported
payment and model evidence using the exported bundle.

## 5. An expertise network: expand beyond a single laptop offer

**The starting choice.** The prototype focuses on one owner-operated expertise
sale so its permissions, payment and recovery behavior can be demonstrated end
to end. It is not presented as a deployed multi-seller marketplace.

**Next scope**

- Separate buyer, expert and broker onboarding across independent wallets.
- Introduce searchable expert offers with transparent prices and access terms.
- Support reusable agent SDKs and richer MCP discovery.
- Add multi-owner isolation, deployment monitoring, gas/key maintenance and
  operational recovery before public hosting.

**Exit evidence:** independent experts and buyers complete purchases with clear
consent, isolated keys, bounded policies and recoverable settlement.

## Development principle

Every milestone should strengthen a property a user can verify: who controls
knowledge, what an agent may spend, how an answer was produced, or whether money
settled. The architecture leaves these responsibilities explicit so they can be
improved independently.

[Current implementation →](ARCHITECTURE.md) · [NEAR integrations →](NEAR_INTEGRATION.md)
