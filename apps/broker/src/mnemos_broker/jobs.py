"""Background jobs for the runs that take minutes rather than seconds.

The red-team set calls the model six times, which takes about forty seconds.
A single HTTP request that long is cut by proxies and keeps a browser waiting,
so the work runs in the background and the caller polls for the result.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Job:
    id: str
    kind: str
    owner: str | None = None
    status: str = "running"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "finished_at": None if self.finished_at is None else self.finished_at.isoformat(),
            "result": self.result,
            "error": self.error,
        }


class JobRegistry:
    """Runs jobs in the background and keeps the last results."""

    def __init__(self, *, keep: int = 50) -> None:
        self._jobs: dict[str, Job] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._keep = keep

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    async def run(
        self, kind: str, work: Callable[[], Awaitable[dict[str, Any]]], *, owner: str | None = None
    ) -> Job:
        job = Job(id=uuid.uuid4().hex, kind=kind, owner=owner)
        self._jobs[job.id] = job
        self._prune()

        async def runner() -> None:
            try:
                result = await work()
                job.result = result
                job.status = "done"
            except Exception:
                job.status = "failed"
                job.error = "The background run failed. Check service health and try again."
                logger.warning("job failed", extra={"job": job.id, "kind": kind})
            finally:
                job.finished_at = datetime.now(UTC)
                self._tasks.pop(job.id, None)
                self._prune()

        self._tasks[job.id] = asyncio.create_task(runner(), name=f"mnemos-job-{job.id}")
        return job

    def _prune(self) -> None:
        if len(self._jobs) <= self._keep:
            return
        finished = [
            job.id
            for job in self._jobs.values()
            if job.finished_at is not None and job.id not in self._tasks
        ]
        for job_id in finished[: len(self._jobs) - self._keep]:
            self._jobs.pop(job_id, None)

    async def close(self) -> None:
        for task in list(self._tasks.values()):
            if not task.done():
                task.cancel()
        self._tasks.clear()
