from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from mnemos_broker.security import sign_session

pytestmark = pytest.mark.integration


async def test_redteam_results_require_the_job_owner(app_factory, settings) -> None:  # type: ignore[no-untyped-def]
    app, _, _ = app_factory(settings=settings)

    async def work() -> dict[str, object]:
        return {
            "simulated": True,
            "scope": "health",
            "model": "test-model",
            "items_considered": 1,
            "attacks": [],
            "note": "sensitive preview",
        }

    job = await app.state.services.jobs.run("redteam", work, owner="owner.testnet")
    await asyncio.sleep(0)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://broker.test"
    ) as client:
        anonymous = await client.get(f"/v1/redteam/run/{job.id}")
        assert anonymous.status_code == 401
        token, _ = sign_session(
            "different.testnet", settings.session_secret_bytes, ttl=timedelta(minutes=5)
        )
        client.cookies.set("mnemos_session", token)
        other = await client.get(f"/v1/redteam/run/{job.id}")
        assert other.status_code == 404
        assert "sensitive" not in other.text
        token, _ = sign_session(
            "owner.testnet", settings.session_secret_bytes, ttl=timedelta(minutes=5)
        )
        client.cookies.set("mnemos_session", token)
        owned = await client.get(f"/v1/redteam/run/{job.id}")
        assert owned.status_code == 200
        assert owned.json()["result"]["note"] == "sensitive preview"
