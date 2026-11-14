# Reproduce from a fresh checkout

The configured laptop starts with `make demo-ready`. A public checkout does
not include private credentials. The README addresses identify the existing
deployment; they do not grant control of those accounts.

## Verify without private credentials

With Docker, Node 22+, pnpm, Python 3.12+/uv, Rust and the Wasm target installed:

```bash
make install
make check
```

This static/unit gate uses explicit fixtures. It does not perform live
inference or submit transactions to the deployed testnet contract.

## Run your own live deployment

1. Copy `.env.example` to `.env`. Supply a NEAR AI Cloud API key, a random
   session secret of at least 32 bytes, and database credentials.
2. Create and fund four **testnet** accounts with a NEAR wallet or CLI:
   contract, owner, agent and broker. Save their credentials privately in
   `.secrets/accounts.json`, replacing all placeholders:

   ```json
   {
     "contract": { "account_id": "your-contract.testnet", "secret_key": "ed25519:YOUR_CONTRACT_KEY" },
     "owner": { "account_id": "your-owner.testnet", "secret_key": "ed25519:YOUR_OWNER_KEY" },
     "agent": { "account_id": "your-agent.testnet", "secret_key": "ed25519:YOUR_AGENT_KEY" },
     "broker": { "account_id": "your-broker.testnet", "secret_key": "ed25519:YOUR_BROKER_KEY" }
   }
   ```

   Scripts require `account_id` and `secret_key`; other fields are optional.
3. Generate the envelope key from the repository root:

   ```bash
   uv run --project apps/broker mnemos-broker keygen --out .secrets/broker_key.json
   ```

   Set `BROKER_X25519_PRIVATE_KEY` to that file's `private_key_b64`,
   `BROKER_NEAR_SECRET_KEY` to the broker's signing key, and
   `BROKER_NEAR_ACCOUNT` to its account id. Fill the four `MNEMOS_*` account
   fields. Use the same contract id in `NEXT_PUBLIC_CONTRACT_ID`, and keep
   both networks `testnet`.
4. With `cargo-near` available, run `make deploy`. It builds, deploys and
   initializes the contract, registers the broker fingerprint and deposits
   demo credit. Accounts must already exist and have enough testnet balance.
   Existing initialized deployments are handled idempotently.
5. Run `make demo-ready`, then open `http://localhost:3000/exchange`. The
   helper checks that `.env` agrees with the saved account ids, enables local
   demo mode and fills missing owner/agent signing configuration. Existing
   notes and balances are preserved.

For regular wallet use, leave `MNEMOS_LOCAL_DEMO=false` and
`NEXT_PUBLIC_DEMO_MODE=false`, start with `make up`, and connect the owner
wallet in Setup. The local signing endpoints remain unavailable.

`make test-e2e` additionally needs the configured running stack, Playwright
browsers and the local demo signer for owner browser flows. Those flows can
perform real red-team inference. The `live`-marked Python tests are separate
opt-in checks, as is the roughly twelve-minute sandbox UTC-day test.

`.env` and `.secrets/` are gitignored. Never include the configured laptop's
secret files in the public repository. Services bind to loopback; this demo
configuration is for a local machine.


## Agent API wallet setup (separate mainnet option)

Run `make agent-api-setup` to create/reuse a partner workspace and owner-signed
buyer/seller policies through the official demo service. The helper uses the
local Git contact identity for partner signup; login credentials, owner key
and API grant tokens stay in ignored `.secrets/` files with mode 0600. Runtime
needs the API key and grant tokens from `.env`, never the setup owner's key.
Re-run setup to renew revoked or expired grants, then restart the broker with
`docker compose up -d --wait broker` so it receives the current environment.

The API reports mainnet, even at its demo URL. On this laptop the user chose to
keep it unfunded. `make agent-api-check` checks the real policy refusals without
funding it. Optional `make agent-api-fund` obtains 1Click funding details; it
does not itself send money. A successful funded purchase/refund is not yet
live-verified. See [NEAR_INTEGRATION.md](NEAR_INTEGRATION.md).

`make agent-key` separately provisions the testnet reader's function-call key.
The original account-management key stays in `accounts.json` for funding and
recovery; it is not placed in the agent runtime. The finite key allowance is
for gas, not the price/budget of an answer.
