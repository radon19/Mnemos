# Submission drafts

Nothing has been posted or submitted. Attach the real demo video and add your
public repository URL before posting.

## Form description

Mnemos — private expertise, paid answers, revocable access.

AI agents need useful knowledge without receiving an entire private notebook. Mnemos lets an expert encrypt notes in the browser, grant one knowledge scope, price each answer, cap reads, set expiry and revoke future access.

The laptop demo runs a real paid read on NEAR testnet through the same ask_memory implementation as our MCP server. The owner-run broker verifies the signed request, decrypts the allowed scope, calls a TEE-hosted model on NEAR AI Cloud with E2EE, filters the answer and settles a hash-only receipt. Failed reads refund the read fee; gas may still apply.

Each inference uses fresh SDK-generated attestation nonces and verified quotes before the prompt is sent. Answers require a provider_tee signature and one matching verified model report. A real negative check proves that changing the nonce fails verification. The local agent uses a separate function-call key restricted to two methods on one contract.

A separate Agent API / NEAR Intents offer implements owner-signed wallet policies, grants, 0.01 USDC transfers, exact settlement checks, durable idempotency and refund recovery. Real destination, transfer-limit and revoked-grant refusals are verified. Its mainnet wallets are intentionally unfunded: successful USDC purchases/refunds and USD-budget rejection are not claimed as live-verified.

Built with Rust near-sdk, FastAPI/Postgres, cross-language encryption, MCP and Next.js. The demo shows a verified answer, real testnet payment, private-scope denial and refusal after revocation.

Trust is explicit: the broker sees plaintext; the contract proves settlement, not inference. Facts can leak through repeated questions. Revocation cannot erase delivered answers.

Tracks: Privacy & Private AI; AI Security & Defense; Agent Economy.
MIT. Independent of sibling project Agent Bureau.

Character count: 1882 (maximum 2,000).

## X post

AI agents can buy an answer without receiving your whole notebook.

Mnemos: scoped access, paid reads, TEE evidence, receipts—and revocation.

Built at NEAR HACKATHON @NEARProtocol #NEARHackathon

Watch the real testnet demo below. Repo link in reply.

Character count: 251 (plain characters; verify in the X composer).

## Before submitting

- Publish the repository with an MIT license and sibling disclosure.
- Attach the MP4 demo or screenshots to the X post. Add the public repository link.
- Include @NEARProtocol, #NEARHackathon and the fact it was built at NEAR HACKATHON.
- Submit repository and demo-post links at https://nearhackathon.com/.
- Use your own/team payout wallet in the form, not a disposable testnet demo account.
- Review every claim against docs/VERIFICATION.md.

Narration, startup and recovery: [DEMO.md](DEMO.md).
