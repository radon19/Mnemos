#!/usr/bin/env python3
"""The Mnemos demo, end to end, against the deployed contract.

The script runs the whole product story and prints the evidence:

1. the owner signs in to the broker with a NEP-413 signature
2. the owner stores an encrypted note in the vault (sealed in this process)
3. the owner creates a grant for the agent on chain
4. the agent asks a question through the MCP server
5. the receipt is shown, on chain
6. the red-team attack set is run against the owner's own vault
7. the owner revokes the grant and the same read is denied

Usage:
    docker compose up -d postgres broker
    pnpm --filter @mnemos/mcp build
    uv run --project apps/broker python scripts/demo.py
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import pathlib
import shutil
import sys
import time
import uuid
from typing import Any

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "broker" / "src"))

from mnemos_broker.crypto import seal_item
from mnemos_broker.near.client import NearClient
from mnemos_broker.near.keys import NearKeyPair, sign_nep413

BROKER_URL = os.environ.get("MNEMOS_BROKER_URL", "http://localhost:8000").rstrip("/")
RPC_URL = os.environ.get("NEAR_RPC_URL", "https://test.rpc.fastnear.com")
PASSPHRASE = os.environ.get("MNEMOS_DEMO_PASSPHRASE", "mnemos-demo-passphrase")
SCOPE = "travel"
QUESTION = "When is my flight, and which hotel am I staying in?"
NOTE = (
    "My flight to Lisbon is on 14 March at 09:15 with reference LX-4417. The hotel is "
    "the Alfama Riverside, near the tram stop, and the confirmation is under my name."
)
GAS = 100_000_000_000_000
PRICE_YOCTO = "10000000000000000000000"  # 0.01 NEAR


def heading(text: str) -> None:
    print(f"\n\033[1m== {text} ==\033[0m")


def info(text: str) -> None:
    print(f"   {text}")


def load_accounts() -> dict[str, Any]:
    path = ROOT / ".secrets" / "accounts.json"
    if not path.exists():
        raise SystemExit("missing .secrets/accounts.json; run scripts/deploy-testnet.sh first")
    data: dict[str, Any] = json.loads(path.read_text())
    return data


async def wait_for_broker(client: httpx.AsyncClient, timeout_seconds: int = 120) -> None:
    """Wait until the broker is ready, so `make demo` can start the stack."""
    deadline = time.monotonic() + timeout_seconds
    last = "no answer"
    while time.monotonic() < deadline:
        try:
            response = await client.get("/readyz")
            if response.status_code == 200:
                return
            last = f"HTTP {response.status_code}"
        except httpx.HTTPError as error:
            last = str(error)
        await asyncio.sleep(2)
    raise SystemExit(f"the broker did not become ready ({last})")


async def broker_session(accounts: dict[str, Any]) -> httpx.AsyncClient:
    client = httpx.AsyncClient(base_url=BROKER_URL, timeout=60.0)
    await wait_for_broker(client)

    owner = accounts["owner"]
    key = NearKeyPair.from_secret_key(owner["secret_key"])
    challenge = (
        await client.post("/v1/auth/challenge", json={"account": owner["account_id"]})
    ).json()
    signature = sign_nep413(
        key,
        message=challenge["message"],
        nonce=bytes.fromhex(challenge["nonce_hex"]),
        recipient=challenge["recipient"],
    )
    response = await client.post(
        "/v1/auth/verify",
        json={
            "account": owner["account_id"],
            "nonce_hex": challenge["nonce_hex"],
            "public_key": key.public_key,
            "signature_b64": base64.b64encode(signature).decode(),
        },
    )
    if response.status_code != 200:
        raise SystemExit(f"the broker refused the sign-in: {response.text}")
    info(f"owner {owner['account_id']} signed the NEP-413 challenge")
    return client


async def store_note(client: httpx.AsyncClient, accounts: dict[str, Any]) -> str:
    identity = (await client.get("/v1/broker/pubkey")).json()
    salt_response = await client.get("/v1/vault/salt")
    if salt_response.status_code == 200:
        owner_salt = base64.b64decode(salt_response.json()["owner_salt_b64"])
    else:
        owner_salt = os.urandom(16)

    envelope = seal_item(
        owner=accounts["owner"]["account_id"],
        scope=SCOPE,
        item_id=str(uuid.uuid4()),
        plaintext=NOTE,
        passphrase=PASSPHRASE,
        owner_salt=owner_salt,
        broker_public_key=base64.b64decode(identity["public_key_b64"]),
    )
    payload = {
        "id": envelope.item_id,
        "scope": envelope.scope,
        "ciphertext_b64": base64.b64encode(envelope.ciphertext).decode(),
        "nonce_b64": base64.b64encode(envelope.nonce).decode(),
        "wrapped_dek_owner_b64": base64.b64encode(envelope.wrapped_dek_owner).decode(),
        "wrapped_dek_broker_b64": base64.b64encode(envelope.wrapped_dek_broker).decode(),
        "content_hash": envelope.content_hash,
        "owner_salt_b64": base64.b64encode(owner_salt).decode(),
    }
    response = await client.post("/v1/vault/items", json=payload)
    if response.status_code != 201:
        raise SystemExit(f"the broker refused the note: {response.text}")
    info(
        f"note {envelope.item_id[:8]} sealed and stored "
        f"(content hash {envelope.content_hash[:16]}…)"
    )
    info(f"broker fingerprint {identity['fingerprint'][:16]}…")
    return envelope.item_id


async def create_grant(accounts: dict[str, Any]) -> str:
    client = NearClient(RPC_URL)
    expires_ns = int(__import__("time").time() * 1_000_000_000) + 86_400 * 1_000_000_000
    tx = await client.send_function_call(
        account_id=accounts["owner"]["account_id"],
        secret_key=accounts["owner"]["secret_key"],
        contract_id=accounts["contract"]["account_id"],
        method="create_grant",
        args={
            "agent": accounts["agent"]["account_id"],
            "scopes": [SCOPE],
            "price": PRICE_YOCTO,
            "daily_cap": 5,
            "expires_ns": str(expires_ns),
            "max_answer_tokens": 256,
        },
        gas=GAS,
    )
    await client.close()
    info(f"grant created for {accounts['agent']['account_id']} on scope {SCOPE}")
    info(f"transaction {tx}")
    return tx


async def ask(accounts: dict[str, Any], question: str) -> tuple[int, dict[str, Any]]:
    environment = {
        **os.environ,
        "MNEMOS_CONTRACT_ID": accounts["contract"]["account_id"],
        "MNEMOS_AGENT_ACCOUNT": accounts["agent"]["account_id"],
        "MNEMOS_AGENT_KEY": accounts["agent"]["secret_key"],
        "MNEMOS_BROKER_URL": BROKER_URL,
        "MNEMOS_BROKER_RECIPIENT": BROKER_URL.replace("http://", "").replace("https://", ""),
        "NEAR_RPC_URL": RPC_URL,
    }
    node = shutil.which("node")
    if node is None:
        raise SystemExit("node is not on the PATH")
    process = await asyncio.create_subprocess_exec(
        node,
        str(ROOT / "apps" / "mcp" / "dist" / "cli.js"),
        "ask",
        "--owner",
        accounts["owner"]["account_id"],
        "--scope",
        SCOPE,
        question,
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        return process.returncode or 1, {"error": stderr.decode().strip()}
    return 0, json.loads(stdout.decode())


async def show_receipts(accounts: dict[str, Any]) -> None:
    client = NearClient(RPC_URL)
    receipts = await client.view_call(
        accounts["contract"]["account_id"],
        "recent_receipts",
        {"owner": accounts["owner"]["account_id"], "from": 0, "limit": 5},
    )
    await client.close()
    for receipt in receipts or []:
        info(
            f"read #{receipt['req_id']} · scope {receipt['scope']} · "
            f"{receipt['price']} yoctoNEAR · hash {receipt['receipt_hash'][:16]}…"
        )


async def run_redteam(client: httpx.AsyncClient) -> None:
    response = await client.post("/v1/redteam/run", json={"scope": SCOPE})
    if response.status_code != 200:
        info(f"the red-team run failed: {response.text}")
        return
    report = response.json()
    info(f"{len(report['attacks'])} attacks against {report['items_considered']} items")
    info(f"model {report['model']} · simulation only, nothing is charged")
    for attack in report["attacks"]:
        info(f"{attack['outcome']:9s} · {attack['label']}")
        info(f"           {attack['reason']}")


async def revoke(accounts: dict[str, Any]) -> str:
    client = NearClient(RPC_URL)
    tx = await client.send_function_call(
        account_id=accounts["owner"]["account_id"],
        secret_key=accounts["owner"]["secret_key"],
        contract_id=accounts["contract"]["account_id"],
        method="revoke_grant",
        args={"agent": accounts["agent"]["account_id"]},
        gas=GAS,
    )
    await client.close()
    info("grant revoked")
    info(f"transaction {tx}")
    return tx


async def main() -> int:
    accounts = load_accounts()

    heading("1. the owner signs in to the broker")
    client = await broker_session(accounts)

    heading("2. the owner stores an encrypted note")
    item_id = await store_note(client, accounts)

    heading("3. the owner grants the agent one scope")
    await create_grant(accounts)

    heading("4. the agent asks a question through the MCP server")
    code, answer = await ask(accounts, QUESTION)
    if code != 0:
        info(f"the read failed: {answer.get('error', 'unknown error')}")
        await client.aclose()
        return 1
    info(f"answer: {answer['answer']}")
    info(f"verified: {answer['verified']}")
    attestation = answer.get("attestation_summary") or {}
    info(f"signature kind: {attestation.get('signature_kind')}")
    info(f"signing address: {attestation.get('signer', {}).get('signing_address', 'unknown')}")
    info(f"TCB status: {attestation.get('tcb_status')}")
    info(f"receipt hash: {answer['receipt_hash']}")
    info(f"receipt transaction: {answer['tx_hash']}")

    heading("5. the receipt on chain")
    await show_receipts(accounts)

    heading("6. the red-team attack set runs against the same vault")
    await run_redteam(client)

    heading("7. the owner revokes the grant")
    await revoke(accounts)

    heading("8. the same read is now denied")
    code, denied = await ask(accounts, QUESTION)
    if code == 0:
        info("the read was served after the revoke, which is a bug")
        await client.aclose()
        return 1
    info(f"denied: {denied.get('error', 'unknown error')}")

    heading("9. the demo note is removed again")
    removed = await client.delete(f"/v1/vault/items/{item_id}")
    info("note deleted" if removed.status_code == 204 else f"could not delete: {removed.text}")

    await client.aclose()
    print("\n\033[1mDemo complete.\033[0m")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
