# Mnemos: private expertise, paid answers

The owner delegated product and engineering choices on 13 November, requested
completion in one run, selected a laptop demo, and authorized existing
credentials and testnet accounts. This design records the chosen scope; no
additional product approval round is needed.

## Intent

Make Mnemos understandable and demonstrable in three minutes: an independent
agent pays an expert for a grounded answer from private knowledge, receives a
verified response and a settlement receipt, and loses future access when the
expert revokes the grant. The laptop represents both independent roles using
distinct real testnet accounts. Sample knowledge is explicitly demo content.

## Approaches

1. Personal memory across assistants: useful, but paying oneself obscures the
   economic purpose.
2. Expert knowledge exchange (selected by the builder under the user's
   delegation): the same existing protocol with an intelligible buyer/seller
   story. Preserve the vault and MCP interfaces and add a guided browser flow.
3. Hosted public marketplace: adds identity, abuse, custody and deployment
   work outside the requested laptop scope. Do not build it.

## Deliverable

- A local-only `/exchange` screen: prepare labeled sample knowledge encrypted
  in the browser, grant the demo agent one scope, ask through the existing MCP
  tools implementation, show real evidence, probe an ungranted scope, revoke,
  and demonstrate an on-chain refusal. The user explicitly triggers each step.
- Scoped local demo routes for status, grant, ask and revoke; no arbitrary
  signing proxy. The owner and agent secrets stay server-side. Routes require
  explicit demo mode, testnet, loopback host, same-origin mutations and an
  authenticated owner session. Remote forwarded requests are refused.
- The demo reuses the existing vault, broker, contract, inference verification
  and MCP tool code. No fake inference, transaction, balance or receipt.
- A deterministic security test suite plus live laptop rehearsal, accessible
  responsive UI, reproducible startup/doctor commands, recorded evidence,
  and a concise demo script and submission material.
- Correct misleading privacy and receipt claims. A chain receipt proves
  settlement by the registered broker, not independent model verification.
  The owner-run broker sees decrypted scope data. Revocation affects future
  access and cannot erase prior answers.

## Constraints and acceptance

Preserve the current Next.js/FastAPI/Rust/MCP architecture, pinned dependencies,
existing visual identity and MIT license. Testnet only. Never disclose or
commit credentials. Keep source files about 400 lines or less. No public
hosting, posting, submission, mainnet spending or protocol redesign. Use live
inference sparingly; the credentials' existing credit is the budget boundary.
Owner operations must keep working outside the guided demo. Offline or failed
dependencies must produce errors, never invented evidence. Avoid mutations on
page load and prevent duplicate submissions. Revocation needs an explicit
confirmation naming the demo agent and consequence.

## Builder choices

Sample expertise: a Lisbon travel specialist's destination dossier (scope
`expertise`) and a separate private business note (`private`). The buyer asks
for a quiet neighborhood and a transport recommendation. Answer facts should
be useful without requiring a verbatim quotation. Price: 0.001 testnet NEAR,
daily cap: 8, expiry: 24 hours, maximum answer tokens: 256. Clearly display
these terms before granting or asking. The existing testnet deployment is
reused if its configuration and broker fingerprint match.
