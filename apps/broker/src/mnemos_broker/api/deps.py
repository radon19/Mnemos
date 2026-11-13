"""FastAPI dependencies: database sessions, owner sessions and rate limits."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import E_RATE_LIMITED, E_UNAUTHORIZED, MnemosError
from ..security import SESSION_COOKIE, SessionClaims, verify_session
from ..services import Services


def get_services(request: Request) -> Services:
    services = getattr(request.app.state, "services", None)
    if not isinstance(services, Services):
        raise MnemosError(500, "E_INTERNAL", "broker services are not initialised")
    return services


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    services = get_services(request)
    async with services.session_factory() as session:
        yield session


def require_owner(request: Request) -> SessionClaims:
    services = get_services(request)
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise MnemosError(401, E_UNAUTHORIZED, "sign in with a NEAR wallet first")
    return verify_session(token, services.settings.session_secret_bytes)


def optional_owner(request: Request) -> SessionClaims | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    services = get_services(request)
    try:
        return verify_session(token, services.settings.session_secret_bytes)
    except MnemosError:
        return None


async def limit_auth(request: Request) -> None:
    services = get_services(request)
    client = request.client.host if request.client else "unknown"
    if not await services.limiter.allow(
        f"auth:{client}",
        capacity=services.settings.auth_rate_limit_per_minute,
        per_seconds=60.0,
    ):
        raise MnemosError(429, E_RATE_LIMITED, "too many authentication attempts; wait a minute")


async def limit_ask(request: Request, agent: str) -> None:
    services = get_services(request)
    if not await services.limiter.allow(
        f"ask:{agent}",
        capacity=services.settings.ask_rate_limit_per_minute,
        per_seconds=60.0,
    ):
        raise MnemosError(429, E_RATE_LIMITED, "too many ask calls; wait a minute")
