# Security and trust

## Control stays with the knowledge owner

Mnemos is built around explicit authority: the owner controls the vault and
knowledge grants; the agent receives bounded access; the broker verifies the
request and inference; NEAR records the economic outcome.

This document describes the current implementation. The [roadmap](ROADMAP.md)
shows how these boundaries can be strengthened next.

## The trust boundaries

| Boundary | Current mechanism | What it establishes |
| --- | --- | --- |
| Browser → storage | Per-item AES-256-GCM encryption with separately wrapped data keys | The stored note body is ciphertext; owner decryption uses the passphrase-derived wrap. |
| Agent → knowledge grant | Named NEAR account, scoped grant, expiry, price and read cap | New testnet requests must satisfy the expert's access terms. |
| Agent runtime → account | Function-call key restricted to one contract and two methods | The reader does not need the account-management key in its runtime. |
| Broker → model host | E2EE to NEAR AI Cloud with fresh verified attestation | Accepted model-hosting evidence is checked before the encrypted prompt is sent. |
| Model → delivered answer | Required `provider_tee` response signature and one matching report | Gateway-only or ambiguous evidence is not accepted as model verification. |
| Buyer → mainnet spending | Owner-signed Agent API policy and runtime grant | The API applies the configured asset, destination and spending controls. |
| Payment → answer | Exact settlement matching, durable checkpoints and idempotency | Submission alone cannot authorize delivery; retry does not intentionally create a fresh charge. |

## What the broker is trusted to do

The broker is **owner-run** and processes selected plaintext to answer a
question. Its encryption key can open all notes wrapped to it. The production
code selects owner and scope only after authorization, but a compromised broker
could bypass that off-chain selection. The chain cannot prevent such decryption.

The owner therefore chooses and trusts the broker deployment. NEAR AI's model
TEE does not make the broker an enclave. Attested broker execution and sealed-key
binding are the next isolation milestone in [the roadmap](ROADMAP.md#2-attested-broker-execution-reduce-trust-in-the-operator).

A compromised registered broker could also falsely settle an approved request.
The receipt is an audit commitment to settlement, not an independent proof that
useful inference occurred.

## What an answer and receipt prove

A successful testnet read provides two distinct kinds of evidence:

1. **Inference evidence:** the broker's pinned SDK verifies hardware/deployment
   evidence, nonce binding and the response signature. Mnemos additionally
   requires the model-serving signature classification and an unambiguous
   matching model report.
2. **Settlement evidence:** the NEAR contract records a receipt commitment and
   transfers the approved read fee to owner earnings.

The contract does not verify TEE quotes. The SDK's exact wire-signature checks
are separate from the application's canonical-projection receipt hash.
Accepted hardware, attestation infrastructure and SDK behavior remain trust
assumptions. Deployment measurements are not a blanket audit of model behavior.

For the USDC offer, the application verifies the official Agent API execution
status against the exact purchase. It does not independently verify that
service's transparency-log proof. A confidential Intents settlement may have an
intent identifier without a public mainnet explorer transaction.

## Access, revocation and answer disclosure

A grant restricts which source category the broker may use. The agent's MCP
interface returns the answer and evidence rather than a vault-dump capability.
A useful answer still communicates facts and may contain short source phrases.

The output policy rejects supported long verbatim reproduction, including
contiguous runs of twelve or more words and checked base64/hex forms. It retries
once with a stricter prompt and withholds the answer if the policy still fails.
Paraphrase, translation and repeated narrow questions remain outside the reach
of a lexical guarantee. The red-team report identifies residual behavior instead
of labeling every attack blocked.

Revocation blocks future authorized access. It cannot erase an answer an agent
already received, and it is not a guarantee that every already-started operation
can be recalled. Cumulative disclosure policies and finer expert-defined answer
rules are planned extensions.

## Keys and sessions

- `.env` and `.secrets/` are ignored by Git. Shared examples contain placeholders.
- The owner's management key and the setup wallet's signing key are not given to
  the agent runtime. Agent API runtime uses scoped grant tokens.
- The local NEAR reader key is restricted to `request_read` and `expire_request`
  on the configured contract. Full-access keys are refused for agent reads.
- The gas allowance must cover the protocol's upfront reservation as well as
  actual execution. It is separate from prepaid read credit and the answer price.
- Owner sign-in uses a single-use NEP-413 challenge. Requests and jobs are bound
  to the authenticated owner; another owner's job cannot be read by guessing its ID.
- Signing out or locking the vault remounts and clears owner query state,
  including displayed answers and revealed note content.

The offline setup helper checks signer identity and signing standard, then
trusts the official service's generated EIP-712 payload. Validating its domain
and operation contents independently is a further setup-hardening opportunity.
The runtime does not hold that owner signing key.

## Money and failure handling

Testnet read fees are reserved before decryption and settled by the registered
broker. Failed/withheld reads follow refund recovery; a pending refund is not
presented as completed. Network gas can still be spent on a failed transaction.

The USDC coordinator persists immutable payment terms and accepted operation
identifiers before polling. A per-read database lock prevents concurrent work;
durable refund intent prevents a crash from turning a refunded purchase into a
free answer. Owner-authorized recovery by ID does not need the original question
or the previous session secret.

The mainnet wallets are intentionally unfunded. Successful USDC payment/refund
and USD-budget rejection are not claimed as live-verified. Their recovery
behavior has deterministic HTTP tests with real Postgres.

## Operating envelope

The shipped rehearsal runs on one laptop with services bound to loopback. Local
signing is explicitly enabled and checks origin, network and owner session. It
is not intended to be exposed through a public tunnel as a hosted custody service.

Rate limiting and activity distribution have shared-Postgres options, but these
do not by themselves establish a production multi-owner deployment. Availability,
key rotation, commerce retention/export, independent API proof verification and
public hosting belong to the rollout milestones.

## Inspect the evidence

- [Verification results](VERIFICATION.md)
- [Live judging evidence](JUDGING_EVIDENCE.json)
- [NEAR integration and code references](NEAR_INTEGRATION.md)
- [Future scope and milestone acceptance criteria](ROADMAP.md)

Use the labeled sample notes for the demonstration. Their public sample
passphrase is for those samples only.
