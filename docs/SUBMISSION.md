# Submission

Drafted, not posted. Nothing here has been sent anywhere.

## Hackathon submission

> **Mnemos — user-owned AI memory with metered, revocable access on NEAR**
>
> You keep your notes. An AI agent can ask questions about them, but only
> through a grant you made on chain: named scopes, a price per read, a daily
> cap, an expiry, and a token budget. Revoke it and the next read fails.
>
> How it works. Your browser encrypts each note with a key derived from your
> passphrase and wraps a copy for the broker's X25519 public key. Plaintext
> never leaves the device, and the database only ever holds ciphertext. When
> an agent asks, the contract charges the agent and creates the read request
> *before* anything is decrypted, so a failed read is refunded, never paid
> for. The broker decrypts exactly one scope, asks NEAR AI Cloud with
> end-to-end encryption, and refuses to use an answer whose TEE attestation
> does not verify. An output filter rejects any answer that reproduces twelve
> or more consecutive words of your memory, then refunds. Every served read
> leaves a hash-only receipt on chain and pays you.
>
> What we shipped. A Rust contract on `near-sdk` 5 with grants, caps, expiry,
> credit, receipts and refunds. A FastAPI broker with a Postgres schema that
> has no column for plaintext. An MCP server with `ask_memory`,
> `list_grants` and `check_credit`, so any MCP client can use it, plus a CLI for
> scripts. A Next.js web app with the vault, the
> grants, a live receipt ledger, earnings and a red-team screen. Cross
> language crypto vectors that both implementations reproduce byte for byte.
>
> What we will not overclaim. The model host cannot read the prompt: the
> completion is end to end encrypted inside an attested TEE. But repeated
> narrow questions can still leak facts, and NEAR's gateway signature does
> not yet chain to the model provider's signature. So the red-team screen
> reports residual risk honestly, and the caps and prices are the mitigation.
>
> Live on NEAR testnet: `mnemos-contract-76badc8e.testnet`.
> MIT licensed, built during the window. Independent of Agent Bureau.

(1,987 characters)

## X post

> Mnemos is live on NEAR testnet: your notes stay encrypted in your browser,
> and an AI agent can only read the scope you granted, at your price, under
> your cap, until you revoke it. Every read leaves a hash-only receipt on
> chain and pays you.
>
> Built with near-sdk 5, NEAR AI Cloud TEE (E2EE + verified attestation),
> FastAPI, and the official MCP SDK.
>
> `mnemos-contract-76badc8e.testnet`
>
> [link to the repository]

(413 characters)

## Demo script

The demo that backs both texts:

1. The owner signs in to the broker with a NEP-413 signature.
2. The owner stores an encrypted note in the `travel` scope.
3. The owner creates a grant for the demo agent: scope `travel`, 0.01 NEAR a
   read, 5 reads a day, one day.
4. The agent asks a question through the MCP server. The answer comes back
   with a `provider_tee` signature, an `UpToDate` TCB status and a receipt
   hash.
5. The receipt is shown on chain.
6. The red-team attack set runs against the same vault.
7. The owner revokes the grant.
8. The same read is denied with `E_GRANT_REVOKED`.

`make demo` runs exactly this and prints the evidence.
