"""Shared pytest fixtures: real Postgres, deterministic chain and inference."""

from __future__ import annotations

import base64
import os
from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from mnemos_broker.app import create_app
from mnemos_broker.config import Settings, get_settings
from mnemos_broker.db import create_session_factory
from mnemos_broker.near.keys import NearKeyPair, b58encode, public_key_bytes_of

from .fakes import FakeChain, FakeInference

TABLES = (
    "commerce_reads, audit_events, auth_challenges, owner_accounts, "
    "read_requests, vault_items, rate_limit_counters"
)


def _test_database_url() -> str:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        parsed = make_url(explicit)
        if "test" not in (parsed.database or ""):
            raise RuntimeError("TEST_DATABASE_URL must point at a database named *test*")
        return explicit
    try:
        base = get_settings().database_url
    except Exception:
        base = "postgresql+asyncpg://mnemos:mnemos@localhost:5432/mnemos"
    parsed = make_url(base)
    return parsed.set(database="mnemos_test").render_as_string(hide_password=False)


def make_settings(database_url: str, **overrides: Any) -> Settings:
    private = X25519PrivateKey.generate().private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    seed = Ed25519PrivateKey.generate()
    values: dict[str, Any] = {
        "mnemos_contract_id": "mnemos-contract.testnet",
        "mnemos_owner_account": "owner.testnet",
        "mnemos_agent_account": "agent.testnet",
        "mnemos_broker_account": "broker.testnet",
        "broker_near_account": "broker.testnet",
        "broker_near_secret_key": SecretStr(
            "ed25519:" + b58encode(seed.private_bytes_raw() + public_key_bytes_of(seed))
        ),
        "broker_x25519_private_key": SecretStr(base64.b64encode(private).decode("ascii")),
        "database_url": database_url,
        "session_secret": SecretStr("test-session-secret-" + "x" * 32),
        "nearai_api_key": SecretStr("test-nearai-key"),
        "nearai_model": "test-model",
        "broker_recipient": "localhost:8000",
        "session_cookie_secure": False,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture(scope="session")
def database_url() -> str:
    return _test_database_url()


@pytest_asyncio.fixture
async def db_engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(database_url, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def clean_db(db_engine: AsyncEngine) -> AsyncIterator[AsyncEngine]:
    async with db_engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    yield db_engine


@pytest.fixture
def settings_factory(database_url: str) -> Callable[..., Settings]:
    def build(**overrides: Any) -> Settings:
        return make_settings(database_url, **overrides)

    return build


@pytest.fixture
def settings(settings_factory: Callable[..., Settings]) -> Settings:
    return settings_factory()


def generate_key() -> NearKeyPair:
    private = Ed25519PrivateKey.generate()
    return NearKeyPair(private_key=private, public_key_bytes=public_key_bytes_of(private))


@pytest.fixture
def owner_key() -> NearKeyPair:
    return generate_key()


@pytest.fixture
def agent_key() -> NearKeyPair:
    return generate_key()


@pytest.fixture
def fake_chain() -> FakeChain:
    return FakeChain()


@pytest.fixture
def fake_inference() -> FakeInference:
    return FakeInference()


AppFactory = Callable[..., tuple[Any, FakeChain, FakeInference]]


@pytest.fixture
def app_factory(settings_factory: Callable[..., Settings], clean_db: AsyncEngine) -> AppFactory:
    def build(
        *,
        settings: Settings | None = None,
        chain: FakeChain | None = None,
        inference: FakeInference | None = None,
        now: Callable[[], Any] | None = None,
    ) -> tuple[Any, FakeChain, FakeInference]:
        configured = settings or settings_factory()
        active_chain = chain or FakeChain()
        active_inference = inference or FakeInference()
        app = create_app(
            configured,
            session_factory=create_session_factory(clean_db),
            engine=clean_db,
            chain=active_chain,
            inference=active_inference,
            now=now,
            start_background=False,
        )
        return app, active_chain, active_inference

    return build


@pytest_asyncio.fixture
async def client(
    settings: Settings,
    app_factory: AppFactory,
    fake_chain: FakeChain,
    fake_inference: FakeInference,
) -> AsyncIterator[AsyncClient]:
    app, _, _ = app_factory(settings=settings, chain=fake_chain, inference=fake_inference)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://broker.test") as http:
        yield http


@pytest.fixture
def execute_sql(clean_db: AsyncEngine):
    async def run(sql: str, **parameters: Any) -> None:
        async with clean_db.begin() as connection:
            await connection.execute(text(sql), parameters)

    return run
