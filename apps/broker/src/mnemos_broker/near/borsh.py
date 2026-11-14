"""The small subset of Borsh needed to build NEAR transactions.

Only function-call, transfer and deploy-contract actions are supported. The
encoding follows the NEAR protocol transaction schema. Tests pin the output
against fixed vectors so a wire-format mistake fails before it reaches chain.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable


def u8(value: int) -> bytes:
    return bytes([value])


def u32(value: int) -> bytes:
    return value.to_bytes(4, "little")


def u64(value: int) -> bytes:
    return value.to_bytes(8, "little")


def u128(value: int) -> bytes:
    return value.to_bytes(16, "little")


def string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return u32(len(encoded)) + encoded


def byte_vec(value: bytes) -> bytes:
    return u32(len(value)) + value


def vec(items: Iterable[bytes]) -> bytes:
    encoded = list(items)
    return u32(len(encoded)) + b"".join(encoded)


def action_function_call(method_name: str, args: bytes, gas: int, deposit: int) -> bytes:
    # Action::FunctionCall = 2
    return u8(2) + string(method_name) + byte_vec(args) + u64(gas) + u128(deposit)


def action_transfer(amount: int) -> bytes:
    # Action::Transfer = 3
    return u8(3) + u128(amount)


def action_deploy_contract(code: bytes) -> bytes:
    # Action::DeployContract = 1
    return u8(1) + byte_vec(code)


def action_add_function_call_key(
    public_key: bytes, receiver: str, methods: list[str], allowance: int
) -> bytes:
    if len(public_key) != 32 or not methods or allowance <= 0:
        raise ValueError("a restricted key needs an Ed25519 key, named methods and gas allowance")
    return (
        u8(5)
        + u8(0)
        + public_key
        + u64(0)
        + u8(0)
        + u8(1)
        + u128(allowance)
        + string(receiver)
        + vec(string(method) for method in methods)
    )


def transaction(
    *,
    signer_id: str,
    public_key: bytes,
    nonce: int,
    receiver_id: str,
    block_hash: bytes,
    actions: list[bytes],
) -> bytes:
    if len(public_key) != 32:
        raise ValueError("ed25519 public key must be 32 bytes")
    if len(block_hash) != 32:
        raise ValueError("block hash must be 32 bytes")
    if not actions:
        raise ValueError("a transaction needs at least one action")
    return (
        string(signer_id)
        + u8(0)
        + public_key
        + u64(nonce)
        + string(receiver_id)
        + block_hash
        + vec(actions)
    )


def signed_transaction(transaction_bytes: bytes, signature: bytes) -> bytes:
    if len(signature) != 64:
        raise ValueError("ed25519 signature must be 64 bytes")
    return transaction_bytes + u8(0) + signature


def encode_actions(actions: list[Callable[[], bytes]]) -> list[bytes]:
    return [action() for action in actions]
