# Verification

## Evidence before claims

Mnemos separates three forms of evidence: reproducible tests, real external
service checks, and the recorded end-to-end demonstration. A passing fixture
is not presented as a live payment. A settlement receipt is not presented as
hardware attestation.

## Automated checks

| Gate | Result | Coverage |
| --- | --- | --- |
| Contract unit tests | 14 passed | Grants, caps, authorization, credit and settlement rules. |
| Crypto tests | 21 passed | Encryption, decryption and shared envelope vectors. |
| Broker unit tests | 104 passed | Request validation, inference policy, key checks, gas readiness and service behavior. |
| MCP tests | 35 passed | Agent tool contract, signing, errors and configuration. |
| Web unit tests | 50 passed | Guarded local routes, exchange terms, sample preparation and formatting. |
| Broker integration tests | 80 passed | Real Postgres with deterministic chain/API/inference boundaries, including recovery regressions. |
| Contract sandbox | 2 passed; 1 explicitly ignored | Lifecycle, negative paths, pause and withdrawals; slow next-day test remains opt-in. |
| Browser suite | 108 passed | Desktop, tablet, mobile, responsive layouts, accessibility, real owner vault flow and live red-team runs. |
| Production builds | Broker and web built | Current Docker images and guarded laptop deployment. |

**224 unit tests pass in total.** `make check` also passes format/lint,
TypeScript checking, Python strict typing and Rust checks.

The full browser suite completed in approximately fifteen minutes. Subsequent
gas-reservation and direct-answer-budget fixes were checked with focused
regressions and a fresh production recording. A final focused browser run
passed 32 additional checks across desktop and mobile, covering accessibility,
payment confirmation/recovery and the guided Exchange. A further real-service
red-team browser run passed after the final model configuration change. The full suite’s live
red-team calls use NEAR AI Cloud credits; they are not mocked model replies.
The USDC interaction tests use clearly labeled HTTP fixtures to exercise money
state without funding the wallet.

```bash
make check
make test-e2e
```

## Fresh external-service checks

[The machine-readable snapshot](JUDGING_EVIDENCE.json) records the actual check
time and the public results.

| Check | Observed result |
| --- | --- |
| Configured model | `Qwen/Qwen3.8-27B` |
| Encrypted inference | `e2ee: true` |
| Response signature | `provider_tee` |
| Matching verified model reports | One |
| TCB status | `UpToDate` in the recorded check |
| GPU evidence | Verified in the recorded check |
| Fresh quote with its original nonce | Verifies successfully |
| Same quote under a changed nonce | Rejected with `binding.nonce_mismatch` |
| Agent API destination rule | Real request rejected: `policy_destination_denied` |
| Agent API per-transfer limit | Real request rejected: `policy_transaction_limit_exceeded` |
| Revoked Agent API runtime grant | Real request rejected: `agent_grant_required` |

These are observations at the recorded time, not promises about every future
model deployment or third-party service response.

```bash
make doctor
make judging-check
```

Doctor additionally checks the configured reader's remaining gas allowance
against both the current gas price and the protocol's upfront purchase-price
floor. The default reservation is 30 Tgas; a positive allowance alone is not
considered sufficient readiness evidence.

## A real paid read through MCP

The direct CLI verification used the existing restricted reader key and the
rebuilt 30 Tgas default:

| Field | Recorded result |
| --- | --- |
| Request | `15` |
| Status | `served` |
| Broker verification | `true` |
| Inference latency | 21,038 ms |
| Receipt commitment | `41d308509aba120b404df7489ebb7a1b2493edfc8ba0be68caca536f8416a6e7` |
| Settlement | [View testnet transaction](https://testnet.nearblocks.io/txns/CEMzPY4w7TJbfpDZ1sZcYSV82bEyTK9BswmsxtUmJQkV) |

The local public record is `artifacts/demo/cli-paid-evidence.json`. It contains
no signing key, cookie or grant token. Testnet NEAR is not mainnet revenue.

## Recorded browser demonstration

The recording script uses the actual application and services without
intercepting network calls:

```bash
make record-demo
```

It checks encrypted sample preparation, a real paid answer and settlement,
ungranted private-scope refusal, revocation, and refusal of the next question.
It also displays the actual separate Agent wallet, checks mobile overflow and
captures the dark theme. A browser error or missing verified payment causes
the recorder to fail.

The latest successful recording's public receipt and model evidence are in
[DEMO_EVIDENCE.json](DEMO_EVIDENCE.json). Local video, screenshots and raw public
response evidence are generated under `artifacts/demo/` and excluded from Git.

## Payment recovery regressions

Independent review identified three Important recovery defects. Each received a
reproducing failing test before its fix:

1. **Crash after an external refund:** durable refund intent prevents returning
   to inference for a refunded payment.
2. **Settlement polling interrupted by grant rotation:** the accepted operation
   ID is saved before polling, so recovery does not require a new transfer POST.
3. **Question/session state lost:** owner-authorized refund recovery uses the
   purchase ID and stored payment terms, without the original question or old
   cookie-signing secret.

Concurrent duplicate requests, consumed reads, exact payment matching and
private-scope/other-owner refusals are also covered. These tests use real
Postgres and deterministic external responses; they establish application
behavior, not a funded mainnet settlement.

## Mainnet activation status

The user chose to leave the Agent API wallets **unfunded**. Consequently:

- A successful mainnet USDC purchase and refund are not live-verified.
- The zero-budget probe is rejected by balance validation before USD-budget
  evaluation, so it is not counted as a successful budget-enforcement test.
- The 1Click deposit helper is implemented, but no funded cross-chain settlement
  is claimed.
- The UI reports Funding needed and disables new mainnet purchases.

The [roadmap](ROADMAP.md#1-mainnet-activation-turn-verified-controls-into-funded-commerce)
defines the evidence needed to complete this activation milestone.

## Repository hygiene

Configured secret values were checked against publishable repository files and
browser assets, with no matches found. `.env`, `.secrets/`, local recordings,
dependency caches and generated test output are excluded from Git. Source,
tests, migrations, lockfiles, asset attribution and reproducible evidence remain.

The final documentation check verifies relative links and balanced fenced code
blocks. The exact SDK and service trust boundaries are documented in
[SECURITY.md](SECURITY.md), with source references in
[NEAR_INTEGRATION.md](NEAR_INTEGRATION.md).
