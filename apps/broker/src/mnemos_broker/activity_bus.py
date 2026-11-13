"""The activity bus, shared by every broker replica.

A read that is served in one replica has to appear in the owner's ledger in
another. The local publisher fans the event out to the subscribers in this
process; the Postgres channel carries it to the other replicas.

Without a database the bus still works, it simply does not cross a process
boundary. That is the honest behaviour for a single-replica deployment.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

from .activity import ActivityPublisher

logger = logging.getLogger(__name__)

CHANNEL = "mnemos_activity"


def _load_asyncpg() -> Any:
    """asyncpg ships no type information; it is used through Any here."""
    import asyncpg  # type: ignore[import-untyped]

    return asyncpg


def asyncpg_dsn(database_url: str) -> str | None:
    """Turns a SQLAlchemy URL into a plain Postgres DSN."""
    if database_url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + database_url[len("postgresql+asyncpg://") :]
    if database_url.startswith("postgresql://"):
        return database_url
    return None


class ActivityBus:
    """Publishes read events locally and, when possible, to every replica."""

    def __init__(self, publisher: ActivityPublisher, database_url: str | None) -> None:
        self.publisher = publisher
        self.dsn = asyncpg_dsn(database_url) if database_url is not None else None
        self._listener: asyncio.Task[None] | None = None
        self._notifier: Any = None
        self._pending: set[asyncio.Task[None]] = set()
        self._listener_connection: Any = None
        self._ready = asyncio.Event()

    async def start(self) -> None:
        if self.dsn is None:
            return
        try:
            asyncpg = _load_asyncpg()

            self._notifier = await asyncpg.connect(self.dsn)
            self._listener = asyncio.create_task(self._listen(), name="mnemos-activity-listener")
            # Do not report the bus as ready before the listener is registered,
            # or the first event can be missed.
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._ready.wait(), timeout=5.0)
        except Exception:
            logger.warning("the activity bus is running locally only", exc_info=True)
            self._notifier = None
            self._listener = None

    async def _listen(self) -> None:
        connection: Any = None
        try:
            asyncpg = _load_asyncpg()

            connection = await asyncpg.connect(self.dsn)
            await connection.add_listener(CHANNEL, self._on_notification)
            self._listener_connection = connection
            self._ready.set()
            # The connection has to stay open: closing it removes the listener.
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("the activity listener stopped", exc_info=True)
        finally:
            if connection is not None:
                with contextlib.suppress(Exception):
                    await connection.close()
            self._listener_connection = None

    def _on_notification(
        self,
        connection: Any,
        pid: int,
        channel: str,
        payload: str,
    ) -> None:
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            return
        owner = event.get("owner")
        if not isinstance(owner, str):
            return
        self.publisher.publish(owner, event)

    def publish(self, owner: str, event: dict[str, Any]) -> None:
        """Hand the event to this process and to the other replicas."""
        self.publisher.publish(owner, event)
        if self._notifier is None:
            return
        task = asyncio.create_task(self._notify(event))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def _notify(self, event: dict[str, Any]) -> None:
        try:
            await self._notifier.execute(
                f"SELECT pg_notify('{CHANNEL}', $1)", json.dumps(event, default=str)
            )
        except Exception:
            logger.warning("the activity event was not shared", exc_info=True)

    async def close(self) -> None:
        for task in list(self._pending):
            task.cancel()
        self._pending.clear()
        if self._listener is not None:
            self._listener.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._listener
            self._listener = None
        if self._notifier is not None:
            with contextlib.suppress(Exception):
                await self._notifier.close()
            self._notifier = None
