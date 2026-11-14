"""Provision one separate runtime key; never alter the offline recovery key."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .access import is_restricted_agent_key
from .borsh import action_add_function_call_key
from .client import NearClient, NearRpcError
from .keys import NearKeyPair, b58encode, public_key_bytes_of

GAS_ALLOWANCE = 50_000_000_000_000_000_000_000  # 0.05 NEAR in gas, not a read budget.


def _saved_key(path: Path, account: str, contract: str) -> str:
    if path.exists():
        saved = json.loads(path.read_text())
        if saved["account_id"] != account or saved["contract_id"] != contract:
            raise ValueError("runtime key belongs to a different deployment")
        secret = str(saved["secret_key"])
    else:
        private = Ed25519PrivateKey.generate()
        secret = "ed25519:" + b58encode(private.private_bytes_raw() + public_key_bytes_of(private))
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write before submitting, so a process interruption never loses a key already added.
        with open(path, "x", opener=lambda p, flags: os.open(p, flags, 0o600)) as output:
            json.dump(
                {"account_id": account, "contract_id": contract, "secret_key": secret}, output
            )
    return secret


async def provision_runtime_key(
    chain: NearClient, *, account: str, contract: str, recovery_key: str, path: Path
) -> str:
    if not account.endswith(".testnet") or not contract.endswith(".testnet"):
        raise ValueError("automatic runtime-key provisioning is testnet-only")
    secret = await asyncio.to_thread(_saved_key, path, account, contract)
    pair = NearKeyPair.from_secret_key(secret)
    try:
        access_key = await chain.view_access_key(account, pair.public_key)
    except NearRpcError as error:
        message = str(error).lower()
        if not any(
            code in message for code in ("unknown_access_key", "unknown key", "does not exist")
        ):
            raise
        await chain.send_actions(
            account_id=account,
            secret_key=recovery_key,
            receiver_id=account,
            actions=[
                action_add_function_call_key(
                    pair.public_key_bytes,
                    contract,
                    ["request_read", "expire_request"],
                    GAS_ALLOWANCE,
                )
            ],
        )
        access_key = await chain.view_access_key(account, pair.public_key)
    if not is_restricted_agent_key(access_key.get("permission"), contract):
        raise ValueError(
            "runtime key is not restricted as expected; provision a new key explicitly"
        )
    return secret
