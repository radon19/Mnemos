"""Typed wrapper around the Mnemos contract.

Every method maps a contract view or call into a small immutable dataclass.
Contract failures are converted to :class:`ContractError` with the stable
``E_*`` code preserved, so the HTTP layer can return the same code the chain
returned instead of inventing a new one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from .config import Settings
from .errors import (
    E_INTERNAL,
    E_KEY_NOT_FOUND,
    MnemosError,
    contract_status,
)
from .near.client import NearClient, NearRpcError, TransactionError

_CONTRACT_CODE_RE = re.compile(r"\bE_[A-Z0-9_]+\b")
_CALL_GAS = 60_000_000_000_000


class ContractError(Exception):
    """A contract rejected a view or call; ``code`` is the stable error code."""

    def __init__(self, code: str, message: str, *, tx_hash: str | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.tx_hash = tx_hash


@dataclass(frozen=True)
class ChainRequest:
    req_id: int
    owner: str
    agent: str
    scope: str
    price: int
    q_hash: str
    status: str
    created_ns: int
    receipt_hash: str | None


@dataclass(frozen=True)
class ChainGrant:
    owner: str
    agent: str
    scopes: tuple[str, ...]
    price: int
    daily_cap: int
    expires_ns: int
    max_answer_tokens: int
    revoked: bool
    used_today: int
    remaining_today: int
    day_index: int


@dataclass(frozen=True)
class ChainBroker:
    broker_account: str
    broker_pubkey_fingerprint: str


@dataclass(frozen=True)
class ChainConfig:
    owner: str
    paused: bool
    next_request_id: int
    request_ttl_ns: int
    day_ns: int


@dataclass(frozen=True)
class ChainReceipt:
    req_id: int
    agent: str
    scope: str
    price: int
    receipt_hash: str
    served_ns: int


class ChainProtocol(Protocol):
    async def close(self) -> None: ...

    async def get_request(self, req_id: int) -> ChainRequest | None: ...

    async def get_grant(self, owner: str, agent: str) -> ChainGrant | None: ...

    async def get_broker(self, owner: str) -> ChainBroker | None: ...

    async def get_config(self) -> ChainConfig: ...

    async def credit_of(self, agent: str) -> int: ...

    async def recent_receipts(self, owner: str, from_: int, limit: int) -> list[ChainReceipt]: ...

    async def record_receipt(self, req_id: int, receipt_hash: str) -> str: ...

    async def refund(self, req_id: int, reason: str) -> str: ...

    async def expire_request(self, req_id: int) -> str: ...

    async def verify_account_key(
        self, account: str, public_key: str, *, require_function_call: bool
    ) -> None: ...

    async def ping(self) -> None: ...


def extract_contract_code(text: str) -> str | None:
    match = _CONTRACT_CODE_RE.search(text)
    return match.group(0) if match else None


def _as_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ContractError(E_INTERNAL, f"contract returned a boolean for {field}")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    raise ContractError(E_INTERNAL, f"contract returned an invalid {field}")


def _as_str(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ContractError(E_INTERNAL, f"contract returned an invalid {field}")
    return value


def _request_from_json(payload: dict[str, Any]) -> ChainRequest:
    receipt_hash = payload.get("receipt_hash")
    return ChainRequest(
        req_id=_as_int(payload.get("id"), "request id"),
        owner=_as_str(payload.get("owner"), "owner"),
        agent=_as_str(payload.get("agent"), "agent"),
        scope=_as_str(payload.get("scope"), "scope"),
        price=_as_int(payload.get("price"), "price"),
        q_hash=_as_str(payload.get("q_hash"), "q_hash"),
        status=_as_str(payload.get("status"), "status"),
        created_ns=_as_int(payload.get("created_ns"), "created_ns"),
        receipt_hash=receipt_hash if isinstance(receipt_hash, str) else None,
    )


def _grant_from_json(payload: dict[str, Any]) -> ChainGrant:
    scopes = payload.get("scopes")
    if not isinstance(scopes, list) or not all(isinstance(scope, str) for scope in scopes):
        raise ContractError(E_INTERNAL, "contract returned invalid grant scopes")
    return ChainGrant(
        owner=_as_str(payload.get("owner"), "owner"),
        agent=_as_str(payload.get("agent"), "agent"),
        scopes=tuple(scopes),
        price=_as_int(payload.get("price"), "price"),
        daily_cap=_as_int(payload.get("daily_cap"), "daily_cap"),
        expires_ns=_as_int(payload.get("expires_ns"), "expires_ns"),
        max_answer_tokens=_as_int(payload.get("max_answer_tokens"), "max_answer_tokens"),
        revoked=bool(payload.get("revoked")),
        used_today=_as_int(payload.get("used_today"), "used_today"),
        remaining_today=_as_int(payload.get("remaining_today"), "remaining_today"),
        day_index=_as_int(payload.get("day_index"), "day_index"),
    )


def _receipt_from_json(payload: dict[str, Any]) -> ChainReceipt:
    return ChainReceipt(
        req_id=_as_int(payload.get("req_id"), "req_id"),
        agent=_as_str(payload.get("agent"), "agent"),
        scope=_as_str(payload.get("scope"), "scope"),
        price=_as_int(payload.get("price"), "price"),
        receipt_hash=_as_str(payload.get("receipt_hash"), "receipt_hash"),
        served_ns=_as_int(payload.get("served_ns"), "served_ns"),
    )


class ChainClient:
    def __init__(self, settings: Settings, *, client: NearClient | None = None) -> None:
        self.settings = settings
        self._client = client or NearClient(settings.near_rpc_url)
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.close()

    async def _view(self, method: str, args: dict[str, Any]) -> Any:
        try:
            return await self._client.view_call(self.settings.mnemos_contract_id, method, args)
        except NearRpcError as error:
            code = extract_contract_code(str(error))
            if code:
                raise ContractError(code, str(error)) from error
            raise ContractError(E_INTERNAL, f"contract view {method} failed") from error

    async def _call(self, method: str, args: dict[str, Any]) -> str:
        try:
            return await self._client.send_function_call(
                account_id=self.settings.broker_near_account,
                secret_key=self.settings.broker_near_secret_key.get_secret_value(),
                contract_id=self.settings.mnemos_contract_id,
                method=method,
                args=args,
                gas=_CALL_GAS,
            )
        except TransactionError as error:
            combined = " ".join([str(error), *error.logs])
            code = extract_contract_code(combined)
            if code:
                raise ContractError(code, combined, tx_hash=error.tx_hash) from error
            raise ContractError(
                E_INTERNAL, f"contract call {method} failed", tx_hash=error.tx_hash
            ) from error
        except NearRpcError as error:
            code = extract_contract_code(str(error))
            if code:
                raise ContractError(code, str(error)) from error
            raise ContractError(E_INTERNAL, f"contract call {method} failed") from error

    async def get_request(self, req_id: int) -> ChainRequest | None:
        payload = await self._view("get_request", {"req_id": req_id})
        if payload is None:
            return None
        if not isinstance(payload, dict):
            raise ContractError(E_INTERNAL, "contract returned an invalid request")
        return _request_from_json(payload)

    async def get_grant(self, owner: str, agent: str) -> ChainGrant | None:
        payload = await self._view("get_grant", {"owner": owner, "agent": agent})
        if payload is None:
            return None
        if not isinstance(payload, dict):
            raise ContractError(E_INTERNAL, "contract returned an invalid grant")
        return _grant_from_json(payload)

    async def get_broker(self, owner: str) -> ChainBroker | None:
        payload = await self._view("get_broker", {"owner": owner})
        if payload is None:
            return None
        if not isinstance(payload, dict):
            raise ContractError(E_INTERNAL, "contract returned an invalid broker")
        return ChainBroker(
            broker_account=_as_str(payload.get("broker_account"), "broker_account"),
            broker_pubkey_fingerprint=_as_str(
                payload.get("broker_pubkey_fingerprint"), "broker_pubkey_fingerprint"
            ),
        )

    async def get_config(self) -> ChainConfig:
        payload = await self._view("get_config", {})
        if not isinstance(payload, dict):
            raise ContractError(E_INTERNAL, "contract returned an invalid config")
        return ChainConfig(
            owner=_as_str(payload.get("owner"), "owner"),
            paused=bool(payload.get("paused")),
            next_request_id=_as_int(payload.get("next_request_id"), "next_request_id"),
            request_ttl_ns=_as_int(payload.get("request_ttl_ns"), "request_ttl_ns"),
            day_ns=_as_int(payload.get("day_ns"), "day_ns"),
        )

    async def credit_of(self, agent: str) -> int:
        payload = await self._view("credit_of", {"agent": agent})
        return _as_int(payload, "credit")

    async def recent_receipts(self, owner: str, from_: int, limit: int) -> list[ChainReceipt]:
        payload = await self._view(
            "recent_receipts", {"owner": owner, "from": from_, "limit": limit}
        )
        if not isinstance(payload, list):
            raise ContractError(E_INTERNAL, "contract returned invalid receipts")
        return [_receipt_from_json(item) for item in payload if isinstance(item, dict)]

    async def record_receipt(self, req_id: int, receipt_hash: str) -> str:
        return await self._call("record_receipt", {"req_id": req_id, "receipt_hash": receipt_hash})

    async def refund(self, req_id: int, reason: str) -> str:
        return await self._call("refund", {"req_id": req_id, "reason": reason})

    async def expire_request(self, req_id: int) -> str:
        return await self._call("expire_request", {"req_id": req_id})

    async def verify_account_key(
        self, account: str, public_key: str, *, require_function_call: bool
    ) -> None:
        try:
            access_key = await self._client.view_access_key(account, public_key)
        except NearRpcError as error:
            raise MnemosError(
                401, E_KEY_NOT_FOUND, "the signing key does not belong to this account"
            ) from error
        permission = access_key.get("permission")
        if isinstance(permission, str) and permission == "FullAccess":
            return
        if isinstance(permission, dict) and "FunctionCall" in permission:
            function_call = permission.get("FunctionCall")
            if isinstance(function_call, dict):
                receiver = function_call.get("receiver_id")
                if (
                    require_function_call
                    and isinstance(receiver, str)
                    and receiver
                    and receiver != self.settings.mnemos_contract_id
                ):
                    raise MnemosError(
                        403,
                        E_KEY_NOT_FOUND,
                        "the signing key is not allowed to call the Mnemos contract",
                    )
            return
        raise MnemosError(401, E_KEY_NOT_FOUND, "the signing key has an unsupported permission")

    async def ping(self) -> None:
        await self.get_config()


def map_contract_error(error: ContractError, *, default_status: int = 409) -> MnemosError:
    """Convert a contract failure into an HTTP error with the same code."""
    status = contract_status(error.code) or default_status
    return MnemosError(status, error.code, error.message)
