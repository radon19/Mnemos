# Trust model

This document says plainly what Mnemos guarantees and what it does not. It is
written for the person who has to decide whether to put their notes in it.

## Who is trusted, and for what

**The owner is the root of trust.** The owner holds the passphrase that wraps
their own copy of every item. The owner controls the grants, the broker, the
deployment and the network. If the owner does not trust their own broker, the
product does not protect them.

**The broker enforces the scope.** The broker is owner-run. It is the only
component that can decrypt a vault item, and it decrypts only the scope named
in the request, only after the contract has charged for that request, and only
for a request that carries the agent's signature. Mnemos does not claim the
broker is trustless. It claims the broker is *bounded*: it has the key for the
items it was given, and the chain, not the broker, decides whether a read is
allowed at all.

**The chain enforces the money and the boundary.** The contract holds the
prepaid credit, the daily caps, the expiry and the grants. It charges before
the broker decrypts, refunds when a read fails, and refuses a request whose
scope, cap, expiry or credit does not check out. A compromised broker cannot
invent a grant, cannot raise a cap and cannot take a read that was not paid
for.

**The model host does not see the prompt or the answer.** The completion runs
with end-to-end encryption against NEAR AI Cloud and comes back with a
provider TEE signature, a signer, a TCB status and a deployment attestation.
The broker calls `verify_response` and discards any answer that does not
verify; there is no unverified fallback path. The host cannot read the
memory.

**The agent sees an answer, not the notes.** The agent receives the answer
text, the receipt hash and the attestation summary. It cannot read the vault,
cannot call the broker for arbitrary scopes and cannot replay a read: the
signature binds the request id, the question, a nonce and the broker, and the
request id can be served once.

## What is not guaranteed

**NEAR's gateway signature does not yet chain to the model provider's
signature.** The response carries a signature from NEAR's gateway and a model
attestation that names the provider's signing key. The two are not yet
cryptographically linked into one chain of custody, so "the provider's model
produced this" rests on the attestation rather than on a single signature
that verifies end to end. The attestation is real evidence and it is what the
broker checks; it is not the same thing as a fully chained proof.

**Repeated narrow questions can still leak facts.** The output filter rejects
any answer that shares a contiguous run of twelve or more words with a
decrypted item, including runs hidden in base64 or hex. That stops bulk
reproduction and verbatim dumps. It does not stop a model from answering
"what is my hotel?" with the hotel's name, because a short answer is not a
twelve-word run. The live red-team run shows exactly this: the model refuses
to copy the memory and then paraphrases it. That is why every grant has a
price and a daily cap, and why the red-team screen reports residual risk
instead of claiming a guarantee.

**A translation of the memory is not a twelve-word run.** The system prompt
forbids translating memory, and the model mostly complies. A lexical filter
cannot detect a faithful translation, so this class stays a residual risk.

**The broker sees the plaintext.** End-to-end encryption protects the prompt
from the model host. It does not hide the memory from the broker, which has
to decrypt it to answer. A malicious or compromised broker can read what it
decrypts. That is the boundary the owner is trusting.

**A compromised owner account is a compromised vault.** The owner key creates
grants and authorises withdrawals. Anyone with the owner's key and the
passphrase can do what the owner can do.

**A compromised agent key can spend the agent's credit.** The key can create
read requests and pay for them. It cannot read the vault without a grant, and
the cap limits the damage.

## The evidence a reader can check

| Claim | Where to check it |
| --- | --- |
| The answer was produced in an attested TEE | The attestation summary on the Activity screen and in `docs/VERIFICATION.md`. |
| The answer came from the owner's scope only | The scope-isolation test in the broker suite and the request that carries the scope. |
| The read was paid for | The receipt on chain: price, scope, request id and hash. |
| The vault cannot be read from the database | `apps/broker/src/mnemos_broker/models.py`: there is no column for plaintext. |
| The agent cannot replay a read | The signature binds the request id, and `read_requests` uses it as a primary key. |
| The bulk attacks are stopped | The red-team suite against a model that tries to comply: `apps/broker/tests/test_redteam.py`. |
| What the filter cannot stop | The live run: `apps/broker/tests/test_live_redteam.py`. |
