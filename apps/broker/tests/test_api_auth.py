from __future__ import annotations

import base64

import pytest
from httpx import ASGITransport, AsyncClient

from mnemos_broker.errors import E_KEY_NOT_FOUND, E_SESSION_EXPIRED
from mnemos_broker.security import SESSION_COOKIE

from .helpers import authenticate, sign_nep413

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_challenge_verify_and_session(client, owner_key) -> None:
    response = await authenticate(client, account="owner.testnet", key=owner_key)
    assert response.status_code == 200, response.text
    assert response.json()["account"] == "owner.testnet"
    assert response.json()["demo"] is False

    session = await client.get("/v1/auth/session")
    assert session.status_code == 200
    assert session.json()["account"] == "owner.testnet"
    cookie = client.cookies.get(SESSION_COOKIE)
    assert cookie is not None


@pytest.mark.asyncio
async def test_challenge_has_exact_shape(client, execute_sql) -> None:
    response = await client.post("/v1/auth/challenge", json={"account": "owner.testnet"})
    assert response.status_code == 200
    body = response.json()
    assert len(bytes.fromhex(body["nonce_hex"])) == 32
    assert len(base64.b64decode(body["nonce_b64"])) == 32
    assert body["message"].startswith("Mnemos sign-in")
    assert body["recipient"] == "localhost:8000"
    assert body["nonce_hex"] in body["message"]


@pytest.mark.asyncio
async def test_challenge_replay_is_rejected(client, owner_key) -> None:
    challenge = await client.post("/v1/auth/challenge", json={"account": "owner.testnet"})
    body = challenge.json()
    payload = {
        "account": "owner.testnet",
        "nonce_hex": body["nonce_hex"],
        "public_key": owner_key.public_key,
        "signature_b64": sign_nep413(
            owner_key,
            message=body["message"],
            nonce=bytes.fromhex(body["nonce_hex"]),
            recipient="localhost:8000",
        ),
    }
    first = await client.post("/v1/auth/verify", json=payload)
    assert first.status_code == 200
    second = await client.post("/v1/auth/verify", json=payload)
    assert second.status_code == 409
    assert second.json()["code"] == "E_CHALLENGE_USED"


@pytest.mark.asyncio
async def test_expired_challenge_is_rejected(client, owner_key, execute_sql) -> None:
    challenge = await client.post("/v1/auth/challenge", json={"account": "owner.testnet"})
    body = challenge.json()
    await execute_sql(
        "UPDATE auth_challenges SET expires_at = now() - interval '1 second' WHERE nonce = :nonce",
        nonce=body["nonce_hex"],
    )
    response = await client.post(
        "/v1/auth/verify",
        json={
            "account": "owner.testnet",
            "nonce_hex": body["nonce_hex"],
            "public_key": owner_key.public_key,
            "signature_b64": sign_nep413(
                owner_key,
                message=body["message"],
                nonce=bytes.fromhex(body["nonce_hex"]),
                recipient="localhost:8000",
            ),
        },
    )
    assert response.status_code == 401
    assert response.json()["code"] == "E_CHALLENGE_EXPIRED"


@pytest.mark.asyncio
async def test_challenge_for_another_account_is_rejected(client, owner_key) -> None:
    challenge = await client.post("/v1/auth/challenge", json={"account": "owner.testnet"})
    body = challenge.json()
    response = await client.post(
        "/v1/auth/verify",
        json={
            "account": "agent.testnet",
            "nonce_hex": body["nonce_hex"],
            "public_key": owner_key.public_key,
            "signature_b64": sign_nep413(
                owner_key,
                message=body["message"],
                nonce=bytes.fromhex(body["nonce_hex"]),
                recipient="localhost:8000",
            ),
        },
    )
    assert response.status_code == 401
    assert response.json()["code"] == "E_UNAUTHORIZED"


@pytest.mark.asyncio
async def test_bad_signature_is_rejected_and_audited(client, owner_key, clean_db) -> None:
    from sqlalchemy import text

    challenge = await client.post("/v1/auth/challenge", json={"account": "owner.testnet"})
    body = challenge.json()
    response = await client.post(
        "/v1/auth/verify",
        json={
            "account": "owner.testnet",
            "nonce_hex": body["nonce_hex"],
            "public_key": owner_key.public_key,
            "signature_b64": base64.b64encode(b"\x00" * 64).decode(),
        },
    )
    assert response.status_code == 401
    assert response.json()["code"] == "E_BAD_SIGNATURE"
    async with clean_db.connect() as connection:
        count = (
            await connection.execute(
                text("SELECT count(*) FROM audit_events WHERE kind = 'auth_failed'")
            )
        ).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_key_not_on_account_is_rejected(
    settings, settings_factory, app_factory, owner_key
) -> None:
    chain = None
    app, chain, _ = app_factory(settings=settings)
    assert chain is not None
    chain.rejected_keys.add(("owner.testnet", owner_key.public_key))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://broker.test") as http:
        response = await authenticate(http, account="owner.testnet", key=owner_key)
    assert response.status_code == 401
    assert response.json()["code"] == E_KEY_NOT_FOUND


@pytest.mark.asyncio
async def test_tampered_session_cookie_is_rejected(client, owner_key) -> None:
    await authenticate(client, account="owner.testnet", key=owner_key)
    token = client.cookies.get(SESSION_COOKIE)
    assert token is not None
    client.cookies.set(SESSION_COOKIE, token[:-1] + ("0" if token[-1] != "0" else "1"))
    response = await client.get("/v1/auth/session")
    assert response.status_code == 401
    assert response.json()["code"] in {"E_UNAUTHORIZED", E_SESSION_EXPIRED}


@pytest.mark.asyncio
async def test_logout_clears_session(client, owner_key) -> None:
    await authenticate(client, account="owner.testnet", key=owner_key)
    assert (await client.get("/v1/auth/session")).status_code == 200
    logout = await client.post("/v1/auth/logout")
    assert logout.status_code == 200
    assert logout.json() == {"ok": True}
    assert (await client.get("/v1/auth/session")).status_code == 401


@pytest.mark.asyncio
async def test_optional_endpoint(client, owner_key) -> None:
    anonymous = await client.get("/v1/auth/optional")
    assert anonymous.json()["authenticated"] is False
    await authenticate(client, account="owner.testnet", key=owner_key)
    authenticated = await client.get("/v1/auth/optional")
    assert authenticated.json() == {
        "authenticated": True,
        "account": "owner.testnet",
        "demo": False,
    }
