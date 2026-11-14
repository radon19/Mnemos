#!/usr/bin/env python3
"""Prepare and diagnose the existing local testnet deployment. Never print secrets."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[1]


async def check_agent_gas_allowance(
    client: httpx.AsyncClient,
    rpc_url: str,
    permission: dict[str, dict[str, object]],
    request_gas: int,
) -> None:
    """Check upfront reservation, including the protocol's gas purchase floor."""
    if not 30_000_000_000_000 <= request_gas <= 300_000_000_000_000:
        raise ValueError("configured agent gas is outside the supported range")

    async def rpc(method: str, params: object) -> dict:
        response = await client.post(
            rpc_url,
            json={"jsonrpc": "2.0", "id": "doctor", "method": method, "params": params},
        )
        response.raise_for_status()
        body = response.json()
        if "error" in body or not isinstance(body.get("result"), dict):
            raise ValueError("gas reservation RPC check failed")
        return body["result"]

    price = await rpc("gas_price", [None])
    protocol = await rpc("EXPERIMENTAL_protocol_config", {"finality": "final"})
    gas_price = max(
        int(price["gas_price"]),
        int(protocol["runtime_config"].get("min_gas_purchase_price", 0)),
    )
    # Leave 2 Tgas for transaction and receipt fees in addition to prepaid gas.
    # The actual request_read transaction uses under 1 Tgas of upfront overhead.
    reservation = (request_gas + 2_000_000_000_000) * gas_price
    allowance = int(str(permission["FunctionCall"]["allowance"]))
    if allowance < reservation:
        raise ValueError("agent allowance cannot cover the configured gas reservation")


def configure() -> None:
    env_path = ROOT / ".env"
    accounts_path = ROOT / ".secrets" / "accounts.json"
    if not env_path.exists() or not accounts_path.exists():
        raise SystemExit(
            "Local credentials are missing. Configure .env and run scripts/deploy-testnet.sh first; never paste keys into terminal output."
        )
    env = dotenv_values(env_path)
    if env.get("NEAR_NETWORK", "testnet") != "testnet":
        raise SystemExit("Refusing to enable the local signer outside testnet.")
    accounts = json.loads(accounts_path.read_text())
    updates = {}
    for role in ("contract", "owner", "agent", "broker"):
        field = (
            "MNEMOS_CONTRACT_ID"
            if role == "contract"
            else f"MNEMOS_{role.upper()}_ACCOUNT"
        )
        account = accounts[role]["account_id"]
        if not account.endswith(".testnet"):
            raise SystemExit("Refusing a non-testnet demo account.")
        if env.get(field) and env[field] != account:
            raise SystemExit(
                f"{field} differs from the existing deployment; reconcile it before enabling the demo."
            )
        updates[field] = account
    if not env.get("NEARAI_API_KEY"):
        raise SystemExit(
            "NEARAI_API_KEY is missing from .env. Add it locally, then retry."
        )
    from mnemos_broker.near.client import NearClient
    from mnemos_broker.near.runtime_key import provision_runtime_key

    async def prepare_key() -> str:
        chain = NearClient(env.get("NEAR_RPC_URL") or "https://test.rpc.fastnear.com")
        try:
            return await provision_runtime_key(
                chain,
                account=accounts["agent"]["account_id"],
                contract=accounts["contract"]["account_id"],
                recovery_key=accounts["agent"]["secret_key"],
                path=ROOT / ".secrets" / "agent_runtime_key.json",
            )
        finally:
            await chain.close()

    runtime_key = asyncio.run(prepare_key())
    updates.update(
        {
            "DEMO_OWNER_SECRET_KEY": env.get("DEMO_OWNER_SECRET_KEY")
            or accounts["owner"]["secret_key"],
            "MNEMOS_AGENT_KEY": runtime_key,
            "MNEMOS_LOCAL_DEMO": "true",
            "NEXT_PUBLIC_DEMO_MODE": "true",
            "NEAR_NETWORK": "testnet",
            "NEXT_PUBLIC_NEAR_NETWORK": "testnet",
            "NEXT_PUBLIC_CONTRACT_ID": accounts["contract"]["account_id"],
            "NEXT_PUBLIC_BROKER_URL": "http://localhost:8000",
            "NEXT_PUBLIC_BROKER_RECIPIENT": env.get("BROKER_RECIPIENT")
            or "localhost:8000",
        }
    )
    for key, value in updates.items():
        set_key(env_path, key, value, quote_mode="always")
    os.chmod(env_path, 0o600)
    print(
        "Local testnet demo configured with a restricted agent key. Recovery key preserved."
    )


async def doctor() -> None:
    env = dotenv_values(ROOT / ".env")
    failed = False
    for flag in ("MNEMOS_LOCAL_DEMO", "NEXT_PUBLIC_DEMO_MODE"):
        enabled = env.get(flag) == "true"
        print(
            f"{'OK' if enabled else 'FAIL'}  {flag}: {'enabled' if enabled else 'disabled; run make demo-ready'}"
        )
        failed |= not enabled
    for key in (
        "NEARAI_API_KEY",
        "BROKER_X25519_PRIVATE_KEY",
        "BROKER_NEAR_SECRET_KEY",
        "DEMO_OWNER_SECRET_KEY",
        "MNEMOS_AGENT_KEY",
    ):
        ok = bool(env.get(key))
        print(f"{'OK' if ok else 'FAIL'}  {key}: {'configured' if ok else 'missing'}")
        failed |= not ok
    async with httpx.AsyncClient(timeout=25) as client:
        for name, url in (
            ("web", "http://localhost:3000/api/health"),
            ("broker", "http://localhost:8000/healthz"),
            ("dependencies", "http://localhost:8000/readyz"),
        ):
            try:
                response = await client.get(url)
                response.raise_for_status()
                print(f"OK  {name}: reachable")
            except httpx.HTTPError:
                failed = True
                print(
                    f"FAIL  {name}: unavailable; run make demo-ready and check docker compose logs"
                )
        try:
            response = await client.get("http://localhost:3000/api/demo/exchange")
            if (
                response.status_code != 401
                or response.json().get("code") != "E_OWNER_SESSION"
            ):
                raise ValueError("local demo runtime is not enabled")
            print(
                "OK  local signing route: enabled, testnet-only and requires owner authentication"
            )
        except (httpx.HTTPError, ValueError):
            failed = True
            print(
                "FAIL  local signing route: runtime flags or local guard mismatch; run make demo-ready"
            )
        try:
            response = await client.get("http://localhost:8000/v1/broker/pubkey")
            response.raise_for_status()
            identity = response.json()
            key = base64.b64decode(identity["public_key_b64"], validate=True)
            fingerprint = hashlib.sha256(key).hexdigest()
            from mnemos_broker.near.client import NearClient
            from mnemos_broker.near.keys import NearKeyPair

            near = NearClient(
                env.get("NEAR_RPC_URL") or "https://test.rpc.fastnear.com"
            )
            try:
                contract = env["MNEMOS_CONTRACT_ID"]
                owner = env["MNEMOS_OWNER_ACCOUNT"]
                broker = await near.view_call(contract, "get_broker", {"owner": owner})
                config = await near.view_call(contract, "get_config", {})
                credit = await near.view_call(
                    contract, "credit_of", {"agent": env["MNEMOS_AGENT_ACCOUNT"]}
                )
                assert (
                    len(key) == 32
                    and fingerprint
                    == broker["broker_pubkey_fingerprint"]
                    == identity["fingerprint"]
                )
                assert broker["broker_account"] == identity["account"]
                assert (
                    identity["contract_id"] == contract
                    and identity["network"] == "testnet"
                )
                assert config["owner"] == owner and not config["paused"]
                assert int(credit) >= 8 * 10**21
                for role, field in (
                    ("owner", "DEMO_OWNER_SECRET_KEY"),
                    ("agent", "MNEMOS_AGENT_KEY"),
                ):
                    pair = NearKeyPair.from_secret_key(env[field] or "")
                    key_status = await near.view_access_key(
                        env[f"MNEMOS_{role.upper()}_ACCOUNT"], pair.public_key
                    )
                    if role == "agent":
                        from mnemos_broker.near.access import is_restricted_agent_key

                        assert is_restricted_agent_key(
                            key_status.get("permission"), contract
                        )
                        try:
                            await check_agent_gas_allowance(
                                client,
                                near.rpc_url,
                                key_status["permission"],
                                int(env.get("MNEMOS_REQUEST_GAS") or "30000000000000"),
                            )
                            print(
                                "OK  agent gas reservation: remaining allowance is sufficient"
                            )
                        except (httpx.HTTPError, ValueError, KeyError, TypeError):
                            failed = True
                            print(
                                "FAIL  agent gas reservation: check MNEMOS_REQUEST_GAS "
                                "(default 30 Tgas), RPC and remaining runtime-key allowance"
                            )
                print(
                    "OK  deployment owner, signing keys, broker binding, testnet and demo credit"
                )
            finally:
                await near.close()
        except Exception:  # noqa: BLE001 — diagnostics must never echo credential-bearing SDK exceptions
            failed = True
            print(
                "FAIL  deployment/key binding or credit check; verify .env against .secrets/deployment.json (details withheld to protect keys)"
            )
    if failed:
        raise SystemExit(1)
    print("Ready: http://localhost:3000/exchange — live testnet; internet is required.")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"configure", "doctor"}:
        raise SystemExit(
            "Usage: uv run --project apps/broker python scripts/laptop.py configure|doctor"
        )
    if sys.argv[1] == "configure":
        configure()
    else:
        asyncio.run(doctor())
