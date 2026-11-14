from __future__ import annotations

from typing import Any

import pytest

from mnemos_broker.chain import (
    ChainClient,
    ContractError,
    extract_contract_code,
    map_contract_error,
)
from mnemos_broker.errors import (
    E_GRANT_REVOKED,
    E_INTERNAL,
    E_KEY_NOT_FOUND,
    E_REQUEST_NOT_FOUND,
)
from mnemos_broker.near.client import NearRpcError, TransactionError


class FakeNear:
    def __init__(self) -> None:
        self.payloads: dict[str, Any] = {}
        self.errors: dict[str, Exception] = {}
        self.access_key: dict[str, Any] = {"permission": "FullAccess"}
        self.access_error: Exception | None = None
        self.sent: list[tuple[str, dict[str, Any]]] = []

    async def view_call(
        self, contract_id: str, method: str, args: dict[str, Any], *, finality: str = "final"
    ) -> Any:
        if method in self.errors:
            raise self.errors[method]
        return self.payloads.get(method)

    async def send_function_call(self, **kwargs: Any) -> str:
        method = str(kwargs["method"])
        if method in self.errors:
            raise self.errors[method]
        self.sent.append((method, kwargs))
        return f"tx-{method}"

    async def view_access_key(self, account_id: str, public_key: str) -> dict[str, Any]:
        if self.access_error is not None:
            raise self.access_error
        return self.access_key


def client(settings) -> tuple[ChainClient, FakeNear]:
    fake = FakeNear()
    return ChainClient(settings, client=fake), fake


def test_extract_contract_code() -> None:
    assert extract_contract_code("failure E_GRANT_REVOKED at line 1") == E_GRANT_REVOKED
    assert extract_contract_code("no code here") is None


@pytest.mark.asyncio
async def test_request_parsing(settings) -> None:
    chain, fake = client(settings)
    fake.payloads["get_request"] = {
        "id": 5,
        "owner": "owner.testnet",
        "agent": "agent.testnet",
        "scope": "health",
        "price": "1000",
        "q_hash": "a" * 64,
        "status": "Approved",
        "created_ns": 123,
        "receipt_hash": None,
    }
    request = await chain.get_request(5)
    assert request is not None
    assert request.req_id == 5
    assert request.price == 1000
    assert request.q_hash == "a" * 64

    fake.payloads["get_request"] = None
    assert await chain.get_request(6) is None


@pytest.mark.asyncio
async def test_request_parsing_rejects_bad_payload(settings) -> None:
    chain, fake = client(settings)
    fake.payloads["get_request"] = {"id": True}
    with pytest.raises(ContractError) as error:
        await chain.get_request(1)
    assert error.value.code == E_INTERNAL


@pytest.mark.asyncio
async def test_grant_and_config_parsing(settings) -> None:
    chain, fake = client(settings)
    fake.payloads["get_grant"] = {
        "owner": "owner.testnet",
        "agent": "agent.testnet",
        "scopes": ["health", "work"],
        "price": 10,
        "daily_cap": 3,
        "expires_ns": 99,
        "max_answer_tokens": 256,
        "revoked": False,
        "used_today": 1,
        "remaining_today": 2,
        "day_index": 4,
    }
    grant = await chain.get_grant("owner.testnet", "agent.testnet")
    assert grant is not None
    assert grant.scopes == ("health", "work")
    assert grant.remaining_today == 2

    fake.payloads["get_config"] = {
        "owner": "owner.testnet",
        "paused": False,
        "next_request_id": 9,
        "request_ttl_ns": 600,
        "day_ns": 86_400,
    }
    config = await chain.get_config()
    assert config.next_request_id == 9
    assert config.paused is False


@pytest.mark.asyncio
async def test_view_error_is_mapped_to_contract_code(settings) -> None:
    chain, fake = client(settings)
    fake.errors["get_config"] = NearRpcError("contract panicked: E_PAUSED")
    with pytest.raises(ContractError) as error:
        await chain.get_config()
    assert error.value.code == "E_PAUSED"


@pytest.mark.asyncio
async def test_send_error_extracts_log_code(settings) -> None:
    chain, fake = client(settings)
    fake.errors["record_receipt"] = TransactionError(
        "txhash", "execution failed", ["log: E_REQUEST_NOT_APPROVED"]
    )
    with pytest.raises(ContractError) as error:
        await chain.record_receipt(1, "a" * 64)
    assert error.value.code == "E_REQUEST_NOT_APPROVED"
    assert error.value.tx_hash == "txhash"


@pytest.mark.asyncio
async def test_access_key_permissions(settings) -> None:
    chain, fake = client(settings)
    # Owner authentication may use a wallet's management key.
    await chain.verify_account_key("owner.testnet", "ed25519:key", require_function_call=False)
    with pytest.raises(Exception) as error:
        await chain.verify_account_key("agent.testnet", "ed25519:key", require_function_call=True)
    assert getattr(error.value, "code", None) == E_KEY_NOT_FOUND

    fake.access_key = {
        "permission": {
            "FunctionCall": {
                "receiver_id": settings.mnemos_contract_id,
                "method_names": ["request_read", "expire_request"],
                "allowance": "50000000000000000000000",
            }
        }
    }
    await chain.verify_account_key("agent.testnet", "ed25519:key", require_function_call=True)

    fake.access_key = {
        "permission": {"FunctionCall": {"receiver_id": "other.testnet", "method_names": []}}
    }
    with pytest.raises(Exception) as error:
        await chain.verify_account_key("agent.testnet", "ed25519:key", require_function_call=True)
    assert getattr(error.value, "code", None) == E_KEY_NOT_FOUND


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "permission",
    [
        {"FunctionCall": {}},
        {"FunctionCall": None},
        {"FunctionCall": {"receiver_id": "mnemos-contract.testnet", "method_names": []}},
        {
            "FunctionCall": {
                "receiver_id": "mnemos-contract.testnet",
                "method_names": ["withdraw_credit"],
            }
        },
        {
            "FunctionCall": {
                "receiver_id": "mnemos-contract.testnet",
                "method_names": ["request_read", "withdraw_credit"],
            }
        },
        {
            "FunctionCall": {
                "receiver_id": "mnemos-contract.testnet",
                "method_names": ["request_read"],
                "allowance": "0",
            }
        },
    ],
)
async def test_agent_key_rejects_unbounded_or_malformed_permissions(settings, permission) -> None:
    chain, fake = client(settings)
    fake.access_key = {"permission": permission}
    with pytest.raises(Exception) as error:
        await chain.verify_account_key("agent.testnet", "ed25519:key", require_function_call=True)
    assert getattr(error.value, "code", None) == E_KEY_NOT_FOUND

    fake.access_key = {"permission": "SomethingElse"}
    with pytest.raises(Exception) as error:
        await chain.verify_account_key("agent.testnet", "ed25519:key", require_function_call=False)
    assert getattr(error.value, "code", None) == E_KEY_NOT_FOUND

    fake.access_error = NearRpcError("unknown key")
    with pytest.raises(Exception) as error:
        await chain.verify_account_key("agent.testnet", "ed25519:key", require_function_call=False)
    assert getattr(error.value, "code", None) == E_KEY_NOT_FOUND


def test_error_mapping_uses_contract_status() -> None:
    mapped = map_contract_error(ContractError(E_GRANT_REVOKED, "revoked"))
    assert mapped.status_code == 403
    assert mapped.code == E_GRANT_REVOKED
    mapped = map_contract_error(ContractError(E_REQUEST_NOT_FOUND, "missing"))
    assert mapped.status_code == 404
