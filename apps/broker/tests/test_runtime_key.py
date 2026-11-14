from __future__ import annotations

import json
from pathlib import Path

import pytest

from mnemos_broker.near import borsh


def test_add_key_wire_format_restricts_receiver_methods_and_gas() -> None:
    # AddKey=5, Ed25519=0, AccessKey.nonce=0, FunctionCall=0, Some allowance=1.
    encoded = borsh.action_add_function_call_key(bytes(range(32)), "app.testnet", ["read"], 100)
    assert encoded.hex() == (
        "0500"
        + "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
        + "0000000000000000"
        + "0001"
        + "64000000000000000000000000000000"
        + "0b0000006170702e746573746e6574"
        + "01000000"
        + "0400000072656164"
    )


@pytest.mark.asyncio
async def test_runtime_provisioning_reuses_saved_key_and_never_replaces_recovery(tmp_path) -> None:
    from mnemos_broker.near.client import NearRpcError
    from mnemos_broker.near.runtime_key import provision_runtime_key

    class Chain:
        permission = None
        adds = 0

        async def view_access_key(self, account, public_key):
            if self.permission is None:
                raise NearRpcError("unknown key")
            return {"permission": self.permission}

        async def send_actions(self, **kwargs):
            assert kwargs["account_id"] == kwargs["receiver_id"] == "agent.testnet"
            assert kwargs["secret_key"] == "offline-recovery-key"
            assert kwargs["actions"][0][0] == 5
            self.adds += 1
            self.permission = {
                "FunctionCall": {
                    "receiver_id": "app.testnet",
                    "method_names": ["request_read", "expire_request"],
                    "allowance": "50000000000000000000000",
                }
            }
            return "actual-add-key-tx"

    path = Path(tmp_path) / "runtime.json"
    chain = Chain()
    first = await provision_runtime_key(
        chain,
        account="agent.testnet",
        contract="app.testnet",
        recovery_key="offline-recovery-key",
        path=path,
    )
    second = await provision_runtime_key(
        chain,
        account="agent.testnet",
        contract="app.testnet",
        recovery_key="offline-recovery-key",
        path=path,
    )
    assert first == second
    assert chain.adds == 1
    assert json.loads(path.read_text())["account_id"] == "agent.testnet"
    assert path.stat().st_mode & 0o777 == 0o600
