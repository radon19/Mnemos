"""Regression for the CLI demo's real asynchronous red-team API contract."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import httpx
import pytest


def load_demo():  # type: ignore[no-untyped-def]
    path = Path(__file__).resolve().parents[3] / "scripts" / "demo.py"
    spec = importlib.util.spec_from_file_location("mnemos_demo", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_demo_waits_for_redteam_job(capsys: pytest.CaptureFixture[str]) -> None:
    def server(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(
                202,
                json={"job_id": "job-one", "status": "running", "poll": "/v1/redteam/run/job-one"},
            )
        return httpx.Response(
            200,
            json={
                "job_id": "job-one",
                "status": "done",
                "result": {
                    "attacks": [
                        {"outcome": "residual", "label": "Paraphrase", "reason": "Lexical limits"}
                    ],
                    "items_considered": 1,
                    "model": "test-model",
                },
            },
        )

    async with httpx.AsyncClient(
        base_url="http://broker", transport=httpx.MockTransport(server)
    ) as client:
        await load_demo().run_redteam(client)
    output = capsys.readouterr().out
    assert "1 attacks" in output
    assert "residual" in output


@pytest.mark.asyncio
async def test_demo_redteam_failure_cannot_be_reported_as_success() -> None:
    async with httpx.AsyncClient(
        base_url="http://broker",
        transport=httpx.MockTransport(lambda _: httpx.Response(503, text="unavailable")),
    ) as client:
        with pytest.raises(SystemExit, match="red-team"):
            await load_demo().run_redteam(client)
