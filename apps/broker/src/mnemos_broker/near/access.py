"""The exact permission boundary of the local memory-reading agent."""

from __future__ import annotations

from typing import Any

AGENT_METHODS = frozenset({"request_read", "expire_request"})


def is_restricted_agent_key(permission: Any, contract: str) -> bool:
    if not isinstance(permission, dict):
        return False
    call = permission.get("FunctionCall")
    if not isinstance(call, dict) or call.get("receiver_id") != contract:
        return False
    methods = call.get("method_names")
    allowance = call.get("allowance")
    return (
        isinstance(methods, list)
        and all(isinstance(method, str) for method in methods)
        and set(methods) == AGENT_METHODS
        and isinstance(allowance, str)
        and allowance.isdecimal()
        and int(allowance) > 0
    )
