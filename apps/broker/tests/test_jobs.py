from __future__ import annotations

import asyncio

from mnemos_broker.jobs import JobRegistry


async def test_finished_jobs_release_tasks_and_respect_retention() -> None:
    registry = JobRegistry(keep=2)

    async def work() -> dict[str, object]:
        return {"done": True}

    ids = []
    for _ in range(4):
        job = await registry.run("redteam", work)
        ids.append(job.id)
        await asyncio.sleep(0)
    assert registry.get(ids[0]) is None
    assert registry.get(ids[1]) is None
    assert registry.get(ids[-1]) is not None
    await registry.close()
