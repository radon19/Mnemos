"""The laptop doctor must reject a key unable to reserve the configured gas."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
from pathlib import Path

import httpx
import pytest


def load_laptop():  # type: ignore[no-untyped-def]
    path = Path(__file__).resolve().parents[3] / "scripts" / "laptop.py"
    spec = importlib.util.spec_from_file_location("mnemos_laptop", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("request_gas", "burn_price", "allowance", "ready"),
    [
        (30_000_000_000_000, 100_000_000, 50_000_000_000_000_000_000_000, True),
        (100_000_000_000_000, 100_000_000, 50_000_000_000_000_000_000_000, False),
        (30_000_000_000_000, 2_000_000_000, 50_000_000_000_000_000_000_000, False),
        (30_000_000_000_000, 100_000_000, 20_000_000_000_000_000_000_000, False),
    ],
)
@pytest.mark.asyncio
async def test_doctor_checks_upfront_purchase_price_and_remaining_allowance(
    request_gas: int, burn_price: int, allowance: int, ready: bool
) -> None:
    def rpc(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body["method"] == "gas_price":
            assert body["params"] == [None]
            result = {"gas_price": str(burn_price)}
        else:
            assert body["method"] == "EXPERIMENTAL_protocol_config"
            assert body["params"] == {"finality": "final"}
            result = {"runtime_config": {"min_gas_purchase_price": "1000000000"}}
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": "doctor", "result": result})

    permission = {
        "FunctionCall": {
            "receiver_id": "app.testnet",
            "method_names": ["request_read", "expire_request"],
            "allowance": str(allowance),
        }
    }
    async with httpx.AsyncClient(transport=httpx.MockTransport(rpc)) as client:
        check = load_laptop().check_agent_gas_allowance(
            client, "https://rpc.test", permission, request_gas
        )
        if ready:
            await check
        else:
            with pytest.raises(ValueError, match="allowance"):
                await check


@pytest.mark.asyncio
async def test_doctor_does_not_report_ready_when_restricted_key_cannot_reserve_gas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    laptop = load_laptop()
    monkeypatch.setattr(laptop, "ROOT", tmp_path)
    test_key = "ed25519:6Ef6Uap1S82NDKQ35YtjwzKKoPjJ8QDQBEz6JWXUZE3m"
    settings = {
        "MNEMOS_LOCAL_DEMO": "true",
        "NEXT_PUBLIC_DEMO_MODE": "true",
        "NEARAI_API_KEY": "test-only-key",
        "BROKER_X25519_PRIVATE_KEY": "test-only-key",
        "BROKER_NEAR_SECRET_KEY": test_key,
        "DEMO_OWNER_SECRET_KEY": test_key,
        "MNEMOS_AGENT_KEY": test_key,
        "MNEMOS_CONTRACT_ID": "app.testnet",
        "MNEMOS_OWNER_ACCOUNT": "owner.testnet",
        "MNEMOS_AGENT_ACCOUNT": "agent.testnet",
        "MNEMOS_REQUEST_GAS": "100000000000000",
        "NEAR_RPC_URL": "https://rpc.test",
    }
    (tmp_path / ".env").write_text("\n".join(f"{key}={value}" for key, value in settings.items()))
    fingerprint = hashlib.sha256(bytes(range(32))).hexdigest()

    def service(request: httpx.Request) -> httpx.Response:
        if request.url.host == "rpc.test":
            body = json.loads(request.content)
            if body["method"] == "gas_price":
                result = {"gas_price": "100000000"}
            elif body["method"] == "EXPERIMENTAL_protocol_config":
                result = {"runtime_config": {"min_gas_purchase_price": "1000000000"}}
            elif body["params"]["request_type"] == "view_access_key":
                result = {
                    "permission": {
                        "FunctionCall": {
                            "receiver_id": "app.testnet",
                            "method_names": ["request_read", "expire_request"],
                            "allowance": "50000000000000000000000",
                        }
                    }
                }
            else:
                values = {
                    "get_broker": {
                        "broker_pubkey_fingerprint": fingerprint,
                        "broker_account": "broker.testnet",
                    },
                    "get_config": {"owner": "owner.testnet", "paused": False},
                    "credit_of": "100000000000000000000000",
                }
                result = {
                    "result": list(json.dumps(values[body["params"]["method_name"]]).encode())
                }
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": "doctor", "result": result})
        if request.url.path == "/v1/broker/pubkey":
            return httpx.Response(
                200,
                json={
                    "public_key_b64": base64.b64encode(bytes(range(32))).decode(),
                    "fingerprint": fingerprint,
                    "account": "broker.testnet",
                    "contract_id": "app.testnet",
                    "network": "testnet",
                },
            )
        if request.url.path == "/api/demo/exchange":
            return httpx.Response(401, json={"code": "E_OWNER_SESSION"})
        return httpx.Response(200, json={"status": "ok"})

    client_type = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client_type(**kwargs, transport=httpx.MockTransport(service)),
    )
    with pytest.raises(SystemExit) as error:
        await laptop.doctor()
    assert error.value.code == 1
    output = capsys.readouterr().out
    assert "FAIL  agent gas reservation" in output
    assert "Ready:" not in output
