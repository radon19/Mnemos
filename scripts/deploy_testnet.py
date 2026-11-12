#!/usr/bin/env python3
"""Idempotent testnet deployment for the Mnemos contract.

Run through `scripts/deploy-testnet.sh` so the repository root, environment and
uv project are set up correctly. No secret is printed.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ACCOUNTS_FILE = ROOT / ".secrets" / "accounts.json"
BROKER_KEY_FILE = ROOT / ".secrets" / "broker_key.json"
DEPLOYMENT_FILE = ROOT / ".secrets" / "deployment.json"
WASM_FILE = ROOT / "contracts" / "mnemos" / "target" / "near" / "mnemos_contract.wasm"

NEAR = 10**24
GAS = 100 * 10**12


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"missing {path}")
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


async def main() -> int:
    from mnemos_broker.cli import generate_broker_key
    from mnemos_broker.near import NearClient, NearRpcError

    accounts = load_json(ACCOUNTS_FILE)
    contract = accounts["contract"]["account_id"]
    owner = accounts["owner"]["account_id"]
    agent = accounts["agent"]["account_id"]
    broker = accounts["broker"]["account_id"]
    contract_key = accounts["contract"]["secret_key"]
    owner_key = accounts["owner"]["secret_key"]
    agent_key = accounts["agent"]["secret_key"]

    if not BROKER_KEY_FILE.exists():
        generate_broker_key(BROKER_KEY_FILE)
    broker_key = load_json(BROKER_KEY_FILE)
    fingerprint = broker_key["fingerprint"]

    rpc_url = os.environ.get("NEAR_RPC_URL", "https://test.rpc.fastnear.com")
    force_deploy = "--force-deploy" in sys.argv
    if not WASM_FILE.exists():
        raise SystemExit(f"missing wasm at {WASM_FILE}; run cargo near build first")

    client = NearClient(rpc_url)
    deployment: dict[str, Any] = {
        "network": "testnet",
        "rpc_url": rpc_url,
        "contract_id": contract,
        "owner_account": owner,
        "agent_account": agent,
        "broker_account": broker,
        "broker_fingerprint": fingerprint,
        "transactions": {},
    }
    try:
        await client.view_account(contract)
        initialized = True
        try:
            await client.view_call(contract, "get_config", {})
        except NearRpcError:
            initialized = False

        if force_deploy or not initialized:
            print(f"deploying {WASM_FILE.name} to {contract} ...")
            tx = await client.deploy_contract(
                account_id=contract,
                secret_key=contract_key,
                wasm=WASM_FILE.read_bytes(),
            )
            deployment["transactions"]["deploy"] = tx
            print(f"deploy tx: {tx}")
        else:
            print("contract code already deployed; skipping deploy")

        if not initialized:
            print("initializing contract ...")
            tx = await client.send_function_call(
                account_id=contract,
                secret_key=contract_key,
                contract_id=contract,
                method="new",
                args={"owner": owner},
                gas=200 * 10**12,
            )
            deployment["transactions"]["init"] = tx
            print(f"init tx: {tx}")

        config = await client.view_call(contract, "get_config", {})
        if config is None or config.get("owner") != owner:
            raise SystemExit("contract initialization did not produce the expected owner")

        current_broker = await client.view_call(contract, "get_broker", {"owner": owner})
        if (
            current_broker is None
            or current_broker.get("broker_account") != broker
            or current_broker.get("broker_pubkey_fingerprint") != fingerprint
        ):
            print("registering broker ...")
            tx = await client.send_function_call(
                account_id=owner,
                secret_key=owner_key,
                contract_id=contract,
                method="set_broker",
                args={"broker_account": broker, "broker_pubkey_fingerprint": fingerprint},
                gas=GAS,
            )
            deployment["transactions"]["set_broker"] = tx
            print(f"set_broker tx: {tx}")
        else:
            print("broker already registered with the same fingerprint")

        credit = await client.view_call(contract, "credit_of", {"agent": agent})
        credit_amount = int(credit) if credit is not None else 0
        if credit_amount < 2 * NEAR:
            print("funding agent credit ...")
            tx = await client.send_function_call(
                account_id=agent,
                secret_key=agent_key,
                contract_id=contract,
                method="deposit_credit",
                args={},
                gas=GAS,
                deposit=5 * NEAR,
            )
            deployment["transactions"]["deposit_credit"] = tx
            print(f"deposit_credit tx: {tx}")
            credit_amount = int(
                await client.view_call(contract, "credit_of", {"agent": agent}) or 0
            )

        broker_balance = int((await client.view_account(broker))["amount"])
        deployment["agent_credit_yocto"] = str(credit_amount)
        deployment["broker_balance_yocto"] = str(broker_balance)
        DEPLOYMENT_FILE.parent.mkdir(parents=True, exist_ok=True)
        DEPLOYMENT_FILE.write_text(json.dumps(deployment, indent=2) + "\n", encoding="utf-8")
        os.chmod(DEPLOYMENT_FILE, 0o600)

        print()
        print(f"contract id: {contract}")
        print(f"owner:       {owner}")
        print(f"agent:       {agent}")
        print(f"broker:      {broker}")
        print(f"fingerprint: {fingerprint}")
        print(f"agent credit: {credit_amount / NEAR:.4f} NEAR")
        print(f"broker balance: {broker_balance / NEAR:.4f} NEAR")
        print(f"deployment file: {DEPLOYMENT_FILE}")
        if broker_balance < NEAR // 10:
            print("WARNING: broker balance is low; receipts need gas")
        return 0
    finally:
        await client.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
