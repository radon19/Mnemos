"""Uniform error envelope and stable broker error codes."""

from __future__ import annotations

from typing import Final

# Client and transport
E_BAD_REQUEST: Final = "E_BAD_REQUEST"
E_VALIDATION: Final = "E_VALIDATION"
E_UNAUTHORIZED: Final = "E_UNAUTHORIZED"
E_FORBIDDEN: Final = "E_FORBIDDEN"
E_NOT_FOUND: Final = "E_NOT_FOUND"
E_RATE_LIMITED: Final = "E_RATE_LIMITED"
E_PAYLOAD_TOO_LARGE: Final = "E_PAYLOAD_TOO_LARGE"
E_INTERNAL: Final = "E_INTERNAL"

# Auth
E_CHALLENGE_EXPIRED: Final = "E_CHALLENGE_EXPIRED"
E_CHALLENGE_USED: Final = "E_CHALLENGE_USED"
E_BAD_SIGNATURE: Final = "E_BAD_SIGNATURE"
E_KEY_NOT_FOUND: Final = "E_KEY_NOT_FOUND"
E_SESSION_EXPIRED: Final = "E_SESSION_EXPIRED"

# Chain and grants
E_GRANT_NOT_FOUND: Final = "E_GRANT_NOT_FOUND"
E_GRANT_REVOKED: Final = "E_GRANT_REVOKED"
E_GRANT_EXPIRED: Final = "E_GRANT_EXPIRED"
E_SCOPE_DENIED: Final = "E_SCOPE_DENIED"
E_CAP_REACHED: Final = "E_CAP_REACHED"
E_INSUFFICIENT_CREDIT: Final = "E_INSUFFICIENT_CREDIT"
E_NOT_BROKER: Final = "E_NOT_BROKER"
E_PAUSED: Final = "E_PAUSED"
E_REQUEST_NOT_FOUND: Final = "E_REQUEST_NOT_FOUND"
E_REQUEST_NOT_APPROVED: Final = "E_REQUEST_NOT_APPROVED"
E_REQUEST_EXPIRED: Final = "E_REQUEST_EXPIRED"
E_REQUEST_CONSUMED: Final = "E_REQUEST_CONSUMED"
E_AGENT_MISMATCH: Final = "E_AGENT_MISMATCH"
E_Q_HASH_MISMATCH: Final = "E_Q_HASH_MISMATCH"
E_BROKER_KEY_MISMATCH: Final = "E_BROKER_KEY_MISMATCH"

# Serving
E_NO_MEMORY: Final = "E_NO_MEMORY"
E_ITEM_CORRUPT: Final = "E_ITEM_CORRUPT"
E_INFERENCE_FAILED: Final = "E_INFERENCE_FAILED"
E_VERIFICATION_FAILED: Final = "E_VERIFICATION_FAILED"
E_OUTPUT_FILTER: Final = "E_OUTPUT_FILTER"
E_RECEIPT_FAILED: Final = "E_RECEIPT_FAILED"
E_REFUND_FAILED: Final = "E_REFUND_FAILED"

# Vault
E_ITEM_EXISTS: Final = "E_ITEM_EXISTS"
E_ITEM_NOT_FOUND: Final = "E_ITEM_NOT_FOUND"
E_OWNER_NOT_FOUND: Final = "E_OWNER_NOT_FOUND"
E_TOO_MANY_ITEMS: Final = "E_TOO_MANY_ITEMS"
E_INVALID_ENVELOPE: Final = "E_INVALID_ENVELOPE"

CONTRACT_CODES: Final = frozenset(
    {
        E_GRANT_NOT_FOUND,
        E_GRANT_REVOKED,
        E_GRANT_EXPIRED,
        E_SCOPE_DENIED,
        E_CAP_REACHED,
        E_INSUFFICIENT_CREDIT,
        E_NOT_BROKER,
        E_PAUSED,
        E_REQUEST_NOT_FOUND,
        E_REQUEST_NOT_APPROVED,
        E_REQUEST_EXPIRED,
        E_REQUEST_CONSUMED,
        E_Q_HASH_MISMATCH,
    }
)


class MnemosError(Exception):
    """An expected failure that maps to the uniform HTTP error envelope."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def contract_status(code: str) -> int:
    if code in {E_GRANT_REVOKED, E_GRANT_EXPIRED, E_SCOPE_DENIED, E_PAUSED}:
        return 403
    if code in {E_CAP_REACHED, E_INSUFFICIENT_CREDIT}:
        return 429
    if code in {E_REQUEST_NOT_FOUND, E_GRANT_NOT_FOUND, E_OWNER_NOT_FOUND, E_ITEM_NOT_FOUND}:
        return 404
    return 409
