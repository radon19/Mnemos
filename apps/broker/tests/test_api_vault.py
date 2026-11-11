from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from .fakes import FakeInference
from .helpers import authenticate, seal, vault_payload

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_create_list_salt_and_delete(client, owner_key, settings) -> None:
    await authenticate(client, account="owner.testnet", key=owner_key)
    envelope = seal(settings, text="My flight to Lisbon is at nine.")
    created = await client.post("/v1/vault/items", json=vault_payload(envelope))
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["id"] == envelope.item_id
    assert body["scope"] == "health"
    assert body["content_hash"] == envelope.content_hash

    listing = await client.get("/v1/vault/items")
    assert listing.status_code == 200
    assert len(listing.json()["items"]) == 1
    assert listing.json()["next_cursor"] is None

    salt = await client.get("/v1/vault/salt")
    assert salt.status_code == 200
    assert salt.json()["owner_salt_b64"] == vault_payload(envelope)["owner_salt_b64"]

    deleted = await client.delete(f"/v1/vault/items/{envelope.item_id}")
    assert deleted.status_code == 204
    empty = await client.get("/v1/vault/items")
    assert empty.json()["items"] == []
    again = await client.delete(f"/v1/vault/items/{envelope.item_id}")
    assert again.status_code == 404


@pytest.mark.asyncio
async def test_scope_filter_and_pagination(client, owner_key, settings) -> None:
    await authenticate(client, account="owner.testnet", key=owner_key)
    ids: list[str] = []
    for index in range(3):
        envelope = seal(settings, text=f"note {index}", scope="health")
        response = await client.post("/v1/vault/items", json=vault_payload(envelope))
        assert response.status_code == 201
        ids.append(envelope.item_id)
    other = seal(settings, text="work note", scope="work")
    assert (await client.post("/v1/vault/items", json=vault_payload(other))).status_code == 201

    first = await client.get("/v1/vault/items", params={"limit": 2})
    assert first.status_code == 200
    assert len(first.json()["items"]) == 2
    cursor = first.json()["next_cursor"]
    assert cursor is not None
    second = await client.get("/v1/vault/items", params={"limit": 2, "cursor": cursor})
    assert len(second.json()["items"]) == 2
    assert second.json()["next_cursor"] is None

    filtered = await client.get("/v1/vault/items", params={"scope": "work"})
    assert [item["scope"] for item in filtered.json()["items"]] == ["work"]

    invalid = await client.get("/v1/vault/items", params={"cursor": "not-a-cursor"})
    assert invalid.status_code == 400
    assert invalid.json()["code"] == "E_VALIDATION"


@pytest.mark.asyncio
async def test_content_hash_mismatch_is_rejected(client, owner_key, settings) -> None:
    await authenticate(client, account="owner.testnet", key=owner_key)
    payload = vault_payload(seal(settings))
    payload["content_hash"] = "b" * 64
    response = await client.post("/v1/vault/items", json=payload)
    assert response.status_code == 400
    assert response.json()["code"] == "E_INVALID_ENVELOPE"


@pytest.mark.asyncio
async def test_reencryption_for_another_broker_is_rejected(
    client, owner_key, settings_factory
) -> None:
    await authenticate(client, account="owner.testnet", key=owner_key)
    foreign_settings = settings_factory()
    payload = vault_payload(seal(foreign_settings))
    response = await client.post("/v1/vault/items", json=payload)
    assert response.status_code == 400
    assert response.json()["code"] == "E_INVALID_ENVELOPE"


@pytest.mark.asyncio
async def test_salt_mismatch_is_rejected(client, owner_key, settings) -> None:
    await authenticate(client, account="owner.testnet", key=owner_key)
    first = await client.post("/v1/vault/items", json=vault_payload(seal(settings)))
    assert first.status_code == 201
    second = await client.post(
        "/v1/vault/items", json=vault_payload(seal(settings), salt=b"\x09" * 16)
    )
    assert second.status_code == 409
    assert second.json()["code"] == "E_INVALID_ENVELOPE"


@pytest.mark.asyncio
async def test_duplicate_item_id_is_rejected(client, owner_key, settings) -> None:
    await authenticate(client, account="owner.testnet", key=owner_key)
    payload = vault_payload(seal(settings))
    assert (await client.post("/v1/vault/items", json=payload)).status_code == 201
    duplicate = await client.post("/v1/vault/items", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "E_ITEM_EXISTS"


@pytest.mark.asyncio
async def test_vault_is_scoped_to_the_authenticated_owner(client, owner_key, settings) -> None:
    await authenticate(client, account="owner.testnet", key=owner_key)
    envelope = seal(settings, owner="owner.testnet")
    assert (await client.post("/v1/vault/items", json=vault_payload(envelope))).status_code == 201

    from .conftest import generate_key

    other_key = generate_key()
    await authenticate(client, account="other-owner.testnet", key=other_key)
    listing = await client.get("/v1/vault/items")
    assert listing.json()["items"] == []
    result = await client.delete(f"/v1/vault/items/{envelope.item_id}")
    assert result.status_code == 404


@pytest.mark.asyncio
async def test_max_vault_items_setting(settings_factory, app_factory, owner_key) -> None:
    settings = settings_factory(max_vault_items=1)
    app, _, _ = app_factory(settings=settings, inference=FakeInference())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://broker.test") as http:
        await authenticate(http, account="owner.testnet", key=owner_key)
        assert (
            await http.post("/v1/vault/items", json=vault_payload(seal(settings)))
        ).status_code == 201
        over = await http.post("/v1/vault/items", json=vault_payload(seal(settings)))
        assert over.status_code == 409
        assert over.json()["code"] == "E_TOO_MANY_ITEMS"


@pytest.mark.asyncio
async def test_vault_requires_session(client) -> None:
    response = await client.get("/v1/vault/items")
    assert response.status_code == 401
    assert response.json()["code"] == "E_UNAUTHORIZED"
