#!/usr/bin/env python3
"""Provision, fund and exercise Mnemos' real policy-bound Agent API wallets.

Owner keys and partner credentials remain in .secrets with mode 0600. Runtime
receives scoped grant tokens only. Demo API is mainnet; no testnet funds work.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from dotenv import set_key
from eth_account import Account
from eth_account.messages import encode_typed_data

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/broker/src"))
from mnemos_broker.agent_api import AgentApiClient, AgentApiError

BASE = "https://api.demo.agentsonintents.com"
PORTAL = "https://partners.demo.agentsonintents.com"
STATE = ROOT / ".secrets/agent-api-wallets.json"
PARTNER = ROOT / ".secrets/agent-api-partner.json"


def save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(data, output, indent=2)
    os.chmod(path, 0o600)


async def partner_key() -> str:
    data = (
        json.loads(PARTNER.read_text())
        if PARTNER.exists()
        else {
            "name": subprocess.check_output(
                ["git", "config", "user.name"], text=True
            ).strip(),
            "email": subprocess.check_output(
                ["git", "config", "user.email"], text=True
            ).strip(),
            "password": secrets.token_urlsafe(32),
        }
    )
    if data.get("api_key"):
        async with AgentApiClient(BASE, data["api_key"]) as api:
            try:
                await api.request("GET", "/v1/whoami")
                return str(data["api_key"])
            except AgentApiError as error:
                if error.status != 401:
                    raise
    new_account = not PARTNER.exists()
    save(PARTNER, data)
    async with httpx.AsyncClient(
        base_url=PORTAL, headers={"Origin": PORTAL}, timeout=30
    ) as http:
        path = "/api/auth/sign-up/email" if new_account else "/api/auth/sign-in/email"
        body = {
            key: data[key]
            for key in (
                ["email", "password", "name"] if new_account else ["email", "password"]
            )
        }
        result = await http.post(path, json=body)
        if not result.is_success:
            raise SystemExit(
                "Partner authentication failed. Sign in at the demo partner dashboard; no credentials were printed."
            )
        result = await http.post("/api/keys", json={"name": "Mnemos hackathon laptop"})
        if not result.is_success or not result.json().get("token"):
            raise SystemExit("The partner dashboard could not issue a key.")
        data["api_key"] = result.json()["token"]
        data.pop("cookies", None)
        save(PARTNER, data)
    return str(data["api_key"])


def policy(asset: str, destination: str | None) -> dict[str, Any]:
    return {
        "frozen": False,
        "actions": ["transfer"],
        "confidential": True,
        "owner_approval": False,
        "assets": [asset],
        "limits": {"per_transaction": {asset: "100000"}, "daily": {asset: "1000000"}},
        "max_actions_per_hour": 30,
        "destinations": {
            "mode": "only",
            "list": []
            if destination is None
            else [{"action": "transfer", "address": destination, "confidential": True}],
        },
        "budget": {"daily_usd": "1.00", "weekly_usd": "5.00", "monthly_usd": "10.00"},
        "timelock_ms": 0,
    }


async def owner_intent(
    api: AgentApiClient, state: dict[str, Any], body: dict[str, Any]
) -> dict[str, Any]:
    generated = await api.request(
        "POST",
        "/v1/generate-intent",
        body=body,
        key="mnemos-owner:" + secrets.token_hex(16),
    )
    intent = generated["intent"]
    owner = Account.from_key(state["owner_key"])
    # Sign the exact service-generated payload, including its contract domain.
    if (
        intent["standard"] != "eip712"
        or generated["signer"]["address"] != owner.address.lower()
    ):
        raise SystemExit(
            "Unexpected owner-signing standard or identity; nothing was signed."
        )
    signature = (
        "0x"
        + Account.sign_message(
            encode_typed_data(full_message=intent["payload"]), owner.key
        ).signature.hex()
    )
    await api.request(
        "POST",
        "/v1/submit-intent",
        body={
            "type": body["type"],
            "correlation_id": generated["correlation_id"],
            "signed_data": {**intent, "signature": signature},
        },
    )
    return await api.settled(generated["correlation_id"])


async def grant(
    api: AgentApiClient, state: dict[str, Any], role: str, *, temporary: bool = False
) -> tuple[str, dict[str, Any]]:
    token = "ngt_" + secrets.token_urlsafe(32)
    if not temporary:
        state[role]["grant_token"] = token
        save(STATE, state)
    result = await owner_intent(
        api,
        state,
        {
            "type": "grant_issue",
            "agent_id": state[role]["agent_id"],
            "label": "Mnemos refusal check" if temporary else f"Mnemos {role} runtime",
            "credential": hashlib.sha256(token.encode()).hexdigest(),
            "expires_at": (datetime.now(UTC) + timedelta(days=7))
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
        },
    )
    return token, result


async def setup() -> None:
    key = await partner_key()
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    if "owner_key" not in state:
        owner = Account.create()
        state.update(owner_key=owner.key.hex(), owner_address=owner.address.lower())
        save(STATE, state)
    owner = Account.from_key(state["owner_key"])
    async with AgentApiClient(BASE, key) as api:
        network = await api.request("GET", "/v1/network")
        if (
            network["network"] != "mainnet"
            or "evm" not in network["supported_owner_types"]
        ):
            raise SystemExit(
                "This API does not support the expected mainnet EVM-owner setup."
            )
        tokens = (await api.request("GET", "/v1/tokens"))["data"]
        state["asset"] = next(
            t["asset_id"]
            for t in tokens
            if t["symbol"] == "USDC"
            and t["decimals"] == 6
            and t["blockchain"] == "near"
        )
        for role in ("seller", "buyer"):
            if state.get(role, {}).get("status", {}).get("status") != "SUCCESS":
                destination = (
                    state["seller"]["wallet"]["near_account_id"]
                    if role == "buyer"
                    else None
                )
                result = await owner_intent(
                    api,
                    state,
                    {
                        "type": "agent_create",
                        "name": f"Mnemos {role}",
                        "owner": {
                            "type": "evm",
                            "address": owner.address.lower(),
                            "chain_id": 8453,
                            "public_key": owner._key_obj.public_key.to_hex(),
                        },
                        "policy": policy(state["asset"], destination),
                    },
                )
                state[role] = {"agent_id": result["agent_id"], "status": result}
                save(STATE, state)
            state[role]["wallet"] = await api.request(
                "GET", f"/v1/agents/{state[role]['agent_id']}/wallet"
            )
            grants = (
                await api.request("GET", f"/v1/agents/{state[role]['agent_id']}/grants")
            )["data"]
            fingerprint = hashlib.sha256(
                state[role].get("grant_token", "").encode()
            ).hexdigest()
            active = any(
                g["owner_message"]["credential"] == fingerprint
                and not g["revoked_at"]
                and datetime.fromisoformat(g["expires_at"].replace("Z", "+00:00"))
                > datetime.now(UTC)
                for g in grants
            )
            if not active:
                _, state[role]["grant_status"] = await grant(api, state, role)
            save(STATE, state)
        # Seller can only return USDC to the buyer. Owner signs this policy.
        current = await api.request(
            "GET", f"/v1/agents/{state['seller']['agent_id']}/policy"
        )
        desired = policy(state["asset"], state["buyer"]["wallet"]["near_account_id"])
        if current.get("policy") != desired:
            await owner_intent(
                api,
                state,
                {
                    "type": "policy_update",
                    "agent_id": state["seller"]["agent_id"],
                    "expected_revision": current["revision"],
                    "policy": desired,
                },
            )
    for name, value in {
        "AGENT_API_ENABLED": "true",
        "AGENT_API_URL": BASE,
        "AGENT_API_KEY": key,
        "AGENT_API_BUYER_ID": state["buyer"]["agent_id"],
        "AGENT_API_BUYER_GRANT": state["buyer"]["grant_token"],
        "AGENT_API_SELLER_ID": state["seller"]["agent_id"],
        "AGENT_API_SELLER_GRANT": state["seller"]["grant_token"],
        "AGENT_API_BUYER_ACCOUNT": state["buyer"]["wallet"]["near_account_id"],
        "AGENT_API_SELLER_ACCOUNT": state["seller"]["wallet"]["near_account_id"],
        "AGENT_API_ASSET": state["asset"],
    }.items():
        set_key(ROOT / ".env", name, value, quote_mode="always")
    os.chmod(ROOT / ".env", 0o600)
    print(
        "Real Agent API wallets and owner-signed policies configured. Secrets remain local."
    )
    print("Mainnet USDC balance is separate from the existing NEAR testnet credit.")


async def checks() -> None:
    state = json.loads(STATE.read_text())
    key = await partner_key()
    buyer = state["buyer"]
    async with AgentApiClient(BASE, key) as api:
        targets = [
            ("destination", "10000", "unapproved.near", "policy_destination_denied"),
            (
                "per-transaction limit",
                "100001",
                state["seller"]["wallet"]["near_account_id"],
                "policy_transaction_limit_exceeded",
            ),
        ]
        evidence: dict[str, Any] = {
            "network": "mainnet",
            "checked_at": datetime.now(UTC).isoformat(),
            "checks": [],
        }
        for label, amount, recipient, expected in targets:
            try:
                await api.pay(
                    agent=buyer["agent_id"],
                    grant=buyer["grant_token"],
                    asset=state["asset"],
                    amount=amount,
                    recipient=recipient,
                    reference="mnemos-check:" + secrets.token_hex(12),
                )
            except AgentApiError as error:
                if error.code != expected:
                    raise SystemExit(
                        f"FAIL {label}: got {error.code}, expected {expected}"
                    ) from None
                print(f"PASS {label}: {error.code}")
                evidence["checks"].append(
                    {"name": label, "code": error.code, "passed": True}
                )
            else:
                raise SystemExit(f"FAIL {label}: an operation was unexpectedly allowed")
        if "budget_probe" not in state:
            owner = Account.from_key(state["owner_key"])
            bounded = policy(
                state["asset"], state["seller"]["wallet"]["near_account_id"]
            )
            bounded["budget"]["daily_usd"] = "0.00"
            result = await owner_intent(
                api,
                state,
                {
                    "type": "agent_create",
                    "name": "Mnemos zero-budget refusal probe",
                    "owner": {
                        "type": "evm",
                        "address": owner.address.lower(),
                        "chain_id": 8453,
                        "public_key": owner._key_obj.public_key.to_hex(),
                    },
                    "policy": bounded,
                },
            )
            state["budget_probe"] = {"agent_id": result["agent_id"], "status": result}
            save(STATE, state)
            _, state["budget_probe"]["grant_status"] = await grant(
                api, state, "budget_probe"
            )
            save(STATE, state)
        try:
            await api.pay(
                agent=state["budget_probe"]["agent_id"],
                grant=state["budget_probe"]["grant_token"],
                asset=state["asset"],
                amount="10000",
                recipient=state["seller"]["wallet"]["near_account_id"],
                reference="mnemos-budget:" + secrets.token_hex(12),
            )
        except AgentApiError as error:
            if error.code == "spend_budget_exceeded":
                print("PASS USD budget: spend_budget_exceeded")
                evidence["checks"].append(
                    {"name": "USD budget", "code": error.code, "passed": True}
                )
            elif error.code == "insufficient_balance":
                print(
                    "NOT EXERCISED USD budget: service checks the empty balance first; wallets remain unfunded by user choice."
                )
                evidence["checks"].append(
                    {
                        "name": "USD budget",
                        "code": error.code,
                        "passed": False,
                        "reason": "No budget-enforcement claim: unfunded probe was rejected by balance validation.",
                    }
                )
            else:
                raise SystemExit(f"FAIL USD budget: got {error.code}") from None
        else:
            raise SystemExit("FAIL USD budget: operation unexpectedly allowed")
        token, issued = await grant(api, state, "buyer", temporary=True)
        grant_id = issued["details"]["grant"]["grant_id"]
        await owner_intent(
            api,
            state,
            {
                "type": "grant_revoke",
                "agent_id": buyer["agent_id"],
                "grant_id": grant_id,
            },
        )
        try:
            await api.pay(
                agent=buyer["agent_id"],
                grant=token,
                asset=state["asset"],
                amount="10000",
                recipient=state["seller"]["wallet"]["near_account_id"],
                reference="mnemos-revoked:" + secrets.token_hex(12),
            )
        except AgentApiError as error:
            if error.code != "agent_grant_required":
                raise
            print("PASS revoked runtime grant: agent_grant_required")
            evidence["checks"].append(
                {"name": "revoked grant", "code": error.code, "passed": True}
            )
        else:
            raise SystemExit("FAIL revoked grant: payment was allowed")
        balances = await api.request("GET", f"/v1/agents/{buyer['agent_id']}/balances")
        available = next(
            (
                b["available_raw"]
                for b in balances["balances"]
                if b["asset_id"] == state["asset"]
            ),
            "0",
        )
        evidence["available_usdc_atomic"] = available
        print(
            f"Buyer balance: {int(available) / 1_000_000:.6f} USDC. Real purchase {'ready' if int(available) >= 10000 else 'requires funding'}."
        )
        out = ROOT / "artifacts/demo/agent-api-checks.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(evidence, indent=2))


async def funding(chain: str) -> None:
    state = json.loads(STATE.read_text())
    async with AgentApiClient(BASE, await partner_key()) as api:
        tokens = (await api.request("GET", "/v1/tokens"))["data"]
        asset = next(
            t["asset_id"]
            for t in tokens
            if t["symbol"] == "USDC" and t["blockchain"] == chain and t["decimals"] == 6
        )
        submitted = await api.request(
            "POST",
            f"/v1/agents/{state['buyer']['agent_id']}/deposit",
            body={
                "origin_asset": asset,
                "destination_asset": state["asset"],
                "amount": "1000000",
                "confidential": True,
            },
            key="mnemos-funding:" + secrets.token_hex(12),
        )
        result = await api.request(
            "GET",
            "/v1/status",
            params={"correlation_id": submitted["correlation_id"], "wait_ms": 3000},
        )
        details = result.get("details", {})
        address = details.get("deposit_address")
        if not address:
            raise SystemExit(
                f"Deposit address is not ready ({result.get('status')}); run the command again later."
            )
        public = {
            "network": "mainnet",
            "origin_chain": chain,
            "token": "USDC",
            "amount": "1.00",
            "address": address,
            "expires_at": details.get("expires_at"),
            "operation": result["correlation_id"],
            "expected_amount_out_atomic": details.get("expected_amount_out"),
            "status": result["status"],
        }
        (ROOT / "artifacts/demo").mkdir(parents=True, exist_ok=True)
        (ROOT / "artifacts/demo/agent-api-funding.json").write_text(
            json.dumps(public, indent=2)
        )
        print(json.dumps(public, indent=2))
        print(
            "Send exactly 1 USDC on the named chain before expiry. This is real mainnet funding through 1Click."
        )


async def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "setup":
        await setup()
    elif command == "check":
        await checks()
    elif command == "funding":
        await funding(sys.argv[2] if len(sys.argv) > 2 else "base")
    else:
        raise SystemExit("Usage: agent_api.py setup|check|funding [base|near|…]")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except AgentApiError as error:
        raise SystemExit(
            f"Agent API: {error.code}. No credential details were printed."
        ) from None
