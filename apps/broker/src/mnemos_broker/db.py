"""Async SQLAlchemy engine, session factory and the shared declarative base."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy.engine import CursorResult, Result
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for every broker table."""


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        connect_args={"timeout": 10},
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


def affected_rows(result: Result[Any]) -> int:
    """Number of rows an UPDATE/DELETE touched.

    SQLAlchemy's async ``Result`` annotation does not expose ``rowcount`` even
    though the underlying cursor result does. Keep the cast in one place.
    """
    return int(cast("CursorResult[Any]", result).rowcount)
