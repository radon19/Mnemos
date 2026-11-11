from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_healthz(client) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "mnemos-broker"


@pytest.mark.asyncio
async def test_readyz_reports_components(client) -> None:
    response = await client.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["components"] == {
        "database": True,
        "chain": True,
        "near_ai_cloud": True,
    }


@pytest.mark.asyncio
async def test_readyz_is_503_when_inference_is_down(
    settings, app_factory, fake_chain, fake_inference
) -> None:
    fake_inference.is_ready = False
    app, _, _ = app_factory(settings=settings, chain=fake_chain, inference=fake_inference)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://broker.test") as http:
        response = await http.get("/readyz")
    assert response.status_code == 503
    assert response.json()["components"]["near_ai_cloud"] is False


@pytest.mark.asyncio
async def test_error_envelope_and_request_id(client) -> None:
    response = await client.get("/v1/vault/items")
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "E_UNAUTHORIZED"
    assert body["request_id"]
    assert response.headers["x-request-id"] == body["request_id"]


@pytest.mark.asyncio
async def test_unknown_route_uses_envelope(client) -> None:
    response = await client.get("/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["code"] == "E_NOT_FOUND"
