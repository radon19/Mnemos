"""Async NEAR JSON-RPC client with signed transactions.

This is intentionally small: the broker needs function calls, the deploy script
needs a contract deployment, and tests need view calls. It follows the public
NEAR JSON-RPC schema and the protocol's Borsh transaction encoding.
"""

from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

import base58
import httpx

from . import borsh
from .keys import NearKeyPair


class NearRpcError(RuntimeError):
    """The RPC node returned an error."""


class TransactionError(RuntimeError):
    """A transaction was submitted but did not succeed."""

    def __init__(self, tx_hash: str, message: str, logs: list[str]) -> None:
        self.tx_hash = tx_hash
        self.logs = logs
        super().__init__(message)


class NearClient:
    def __init__(self, rpc_url: str, *, timeout_seconds: float = 30.0) -> None:
        self.rpc_url = rpc_url
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            headers={"content-type": "application/json"},
        )
        self._nonces: dict[str, int] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def close(self) -> None:
        await self._http.aclose()

    async def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        response = await self._http.post(
            self.rpc_url,
            json={"jsonrpc": "2.0", "id": "mnemos", "method": method, "params": params},
        )
        try:
            body = response.json()
        except ValueError as error:
            raise NearRpcError(f"RPC returned non-JSON ({response.status_code})") from error
        if not isinstance(body, dict):
            raise NearRpcError("RPC returned an unexpected payload")
        if "error" in body:
            raise NearRpcError(_stringify_rpc_error(body["error"]))
        result = body.get("result")
        if not isinstance(result, dict):
            raise NearRpcError("RPC response is missing a result object")
        return result

    async def view_call(
        self,
        contract_id: str,
        method: str,
        args: dict[str, Any],
        *,
        finality: str = "final",
    ) -> Any:
        result = await self._rpc(
            "query",
            {
                "request_type": "call_function",
                "finality": finality,
                "account_id": contract_id,
                "method_name": method,
                "args_base64": base64.b64encode(
                    json.dumps(args, separators=(",", ":")).encode("utf-8")
                ).decode("ascii"),
            },
        )
        call_error = result.get("error")
        if isinstance(call_error, str):
            raise NearRpcError(call_error)
        raw = result.get("result")
        if isinstance(raw, list):
            data = bytes(int(byte) for byte in raw)
        elif isinstance(raw, str):
            data = base64.b64decode(raw)
        else:
            raise NearRpcError("call_function result has an unexpected shape")
        if not data:
            return None
        return json.loads(data.decode("utf-8"))

    async def view_access_key(self, account_id: str, public_key: str) -> dict[str, Any]:
        return await self._rpc(
            "query",
            {
                "request_type": "view_access_key",
                "finality": "optimistic",
                "account_id": account_id,
                "public_key": public_key,
            },
        )

    async def view_account(self, account_id: str) -> dict[str, Any]:
        return await self._rpc(
            "query",
            {
                "request_type": "view_account",
                "finality": "optimistic",
                "account_id": account_id,
            },
        )

    async def _latest_block_hash(self) -> bytes:
        result = await self._rpc("block", {"finality": "final"})
        header = result.get("header")
        if not isinstance(header, dict) or not isinstance(header.get("hash"), str):
            raise NearRpcError("block response is missing header.hash")
        return base58.b58decode(header["hash"])

    def _lock_for(self, account_id: str) -> asyncio.Lock:
        lock = self._locks.get(account_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[account_id] = lock
        return lock

    async def _next_nonce(self, account_id: str, public_key: str) -> int:
        cached = self._nonces.get(account_id)
        if cached is not None:
            return cached + 1
        access_key = await self.view_access_key(account_id, public_key)
        nonce = access_key.get("nonce")
        if not isinstance(nonce, int):
            raise NearRpcError("access key response is missing nonce")
        return nonce + 1

    async def send_actions(
        self,
        *,
        account_id: str,
        secret_key: str,
        receiver_id: str,
        actions: list[bytes],
        wait_until: str = "FINAL",
    ) -> str:
        key = NearKeyPair.from_secret_key(secret_key)
        async with self._lock_for(account_id):
            last_error: Exception | None = None
            for attempt in range(3):
                try:
                    nonce = await self._next_nonce(account_id, key.public_key)
                    block_hash = await self._latest_block_hash()
                    tx = borsh.transaction(
                        signer_id=account_id,
                        public_key=key.public_key_bytes,
                        nonce=nonce,
                        receiver_id=receiver_id,
                        block_hash=block_hash,
                        actions=actions,
                    )
                    signature = key.sign_transaction(tx)
                    signed = base64.b64encode(borsh.signed_transaction(tx, signature)).decode(
                        "ascii"
                    )
                    result = await self._rpc(
                        "send_tx",
                        {"signed_tx_base64": signed, "wait_until": wait_until},
                    )
                    if "final_execution_outcome" in result:
                        result = result["final_execution_outcome"]
                    status = result.get("status")
                    if isinstance(status, dict) and "Failure" in status:
                        logs = _collect_logs(result)
                        tx_hash = _transaction_hash(result)
                        raise TransactionError(
                            tx_hash,
                            f"transaction failed: {logs[-1] if logs else status}",
                            logs,
                        )
                    self._nonces[account_id] = nonce
                    return _transaction_hash(result)
                except NearRpcError as error:
                    last_error = error
                    self._nonces.pop(account_id, None)
                    if "nonce" not in str(error).lower() or attempt == 2:
                        raise
                    await asyncio.sleep(0.4 * (attempt + 1))
            raise NearRpcError(f"transaction failed after retries: {last_error}")

    async def send_function_call(
        self,
        *,
        account_id: str,
        secret_key: str,
        contract_id: str,
        method: str,
        args: dict[str, Any],
        gas: int,
        deposit: int = 0,
        wait_until: str = "FINAL",
    ) -> str:
        encoded_args = json.dumps(args, separators=(",", ":")).encode("utf-8")
        action = borsh.action_function_call(method, encoded_args, gas, deposit)
        return await self.send_actions(
            account_id=account_id,
            secret_key=secret_key,
            receiver_id=contract_id,
            actions=[action],
            wait_until=wait_until,
        )

    async def deploy_contract(
        self,
        *,
        account_id: str,
        secret_key: str,
        wasm: bytes,
        wait_until: str = "FINAL",
    ) -> str:
        action = borsh.action_deploy_contract(wasm)
        return await self.send_actions(
            account_id=account_id,
            secret_key=secret_key,
            receiver_id=account_id,
            actions=[action],
            wait_until=wait_until,
        )

    async def transfer(
        self,
        *,
        account_id: str,
        secret_key: str,
        receiver_id: str,
        amount: int,
        wait_until: str = "FINAL",
    ) -> str:
        return await self.send_actions(
            account_id=account_id,
            secret_key=secret_key,
            receiver_id=receiver_id,
            actions=[borsh.action_transfer(amount)],
            wait_until=wait_until,
        )


def _transaction_hash(result: dict[str, Any]) -> str:
    transaction = result.get("transaction")
    if isinstance(transaction, dict):
        tx_hash = transaction.get("hash")
        if isinstance(tx_hash, str):
            return tx_hash
    outcome = result.get("transaction_outcome")
    if isinstance(outcome, dict):
        outcome_id = outcome.get("id")
        if isinstance(outcome_id, str):
            return outcome_id
    return ""


def _collect_logs(result: dict[str, Any]) -> list[str]:
    logs: list[str] = []
    outcomes = result.get("receipts_outcome")
    if not isinstance(outcomes, list):
        return logs
    for receipt in outcomes:
        if not isinstance(receipt, dict):
            continue
        outcome = receipt.get("outcome")
        if isinstance(outcome, dict):
            receipt_logs = outcome.get("logs")
            if isinstance(receipt_logs, list):
                logs.extend(str(line) for line in receipt_logs)
    return logs


def _stringify_rpc_error(error: Any) -> str:
    if isinstance(error, dict):
        for key in ("cause", "data", "message"):
            value = error.get(key)
            if isinstance(value, (str, dict, list)):
                return json.dumps(value, sort_keys=True)
    return str(error)
