"""The broker's own HTTP client, against a mocked NEAR RPC node.

The tests use respx so the real request and response shapes of the public JSON
RPC are exercised: the `query` method for views, the `send_tx` method for
transactions, and the error shapes a node returns when a call panics.
"""

from __future__ import annotations

import base64
import json

import base58
import pytest
import respx
from httpx import Response

from mnemos_broker.near.client import NearClient, NearRpcError

RPC_URL = "https://rpc.test.near.invalid"
CONTRACT = "mnemos-contract.testnet"
BLOCK_HASH = base58.b58encode(bytes(range(32))).decode()


def rpc_result(payload: object) -> Response:
    body = {
        "jsonrpc": "2.0",
        "id": "mnemos",
        "result": payload,
    }
    return Response(200, json=body)


def view_result(value: object) -> Response:
    encoded = base64.b64encode(json.dumps(value).encode()).decode()
    return rpc_result({"result": encoded})


@pytest.mark.asyncio
@respx.mock
async def test_view_call_decodes_the_result() -> None:
    route = respx.post(RPC_URL).mock(
        return_value=view_result({"owner": "owner.testnet", "paused": False})
    )
    client = NearClient(RPC_URL)
    try:
        value = await client.view_call(CONTRACT, "get_config", {})
    finally:
        await client.close()
    assert value == {"owner": "owner.testnet", "paused": False}
    request_body = json.loads(route.calls[0].request.content.decode())
    assert request_body["method"] == "query"
    assert request_body["params"]["method_name"] == "get_config"
    assert request_body["params"]["account_id"] == CONTRACT


@pytest.mark.asyncio
@respx.mock
async def test_view_call_reports_an_rpc_error() -> None:
    respx.post(RPC_URL).mock(
        return_value=Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": "mnemos",
                "error": {"name": "HANDLER_ERROR", "cause": {"name": "ContractPanic"}},
            },
        )
    )
    client = NearClient(RPC_URL)
    try:
        with pytest.raises(NearRpcError):
            await client.view_call(CONTRACT, "get_config", {})
    finally:
        await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_access_key_is_read_from_the_node() -> None:
    respx.post(RPC_URL).mock(
        return_value=rpc_result(
            {
                "nonce": 7,
                "permission": "FullAccess",
                "block_hash": "hash",
                "block_height": 100,
            }
        )
    )
    client = NearClient(RPC_URL)
    try:
        access_key = await client.view_access_key(
            "agent.testnet", "ed25519:6Ef6Uap1S82NDKQ35YtjwzKKoPjJ8QDQBEz6JWXUZE3m"
        )
    finally:
        await client.close()
    assert access_key["permission"] == "FullAccess"
    assert access_key["nonce"] == 7


def _node_responses(request) -> Response:
    """Answers the access key query first, then the transaction."""
    body = json.loads(request.content.decode())
    if body["method"] == "query":
        return rpc_result(
            {
                "nonce": 7,
                "permission": "FullAccess",
                "block_hash": "hash",
                "block_height": 100,
            }
        )
    if body["method"] == "block":
        return rpc_result(
            {
                "header": {"hash": BLOCK_HASH, "height": 100, "epoch_id": "epoch"},
                "chunks": [],
            }
        )
    return rpc_result(
        {
            "transaction": {"hash": "tx"},
            "status": {
                "Failure": {
                    "ActionError": {
                        "kind": {
                            "FunctionCallError": {
                                "ExecutionError": (
                                    "Smart contract panicked: E_GRANT_REVOKED: "
                                    "grant has been revoked"
                                )
                            }
                        }
                    }
                }
            },
        }
    )


@pytest.mark.asyncio
@respx.mock
async def test_a_failed_transaction_keeps_the_contract_code() -> None:
    respx.post(RPC_URL).mock(side_effect=_node_responses)
    client = NearClient(RPC_URL)
    try:
        with pytest.raises(Exception) as error:
            await client.send_function_call(
                account_id="owner.testnet",
                secret_key="ed25519:6Ef6Uap1S82NDKQ35YtjwzKKoPjJ8QDQBEz6JWXUZE3m",
                contract_id=CONTRACT,
                method="create_grant",
                args={"agent": "agent.testnet"},
                gas=100_000_000_000_000,
            )
    finally:
        await client.close()
    assert "E_GRANT_REVOKED" in str(error.value)
