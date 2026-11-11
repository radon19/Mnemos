"""FastAPI application factory and cross-cutting middleware."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import re
import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import structlog
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from .activity import ActivityPublisher
from .api import activity, ask, auth, broker, health, redteam, vault
from .chain import ChainClient, ChainProtocol
from .config import Settings, get_settings
from .db import create_engine, create_session_factory
from .errors import E_BAD_REQUEST, E_INTERNAL, E_NOT_FOUND, E_PAYLOAD_TOO_LARGE, MnemosError
from .inference import InferenceProtocol, NearAiInferenceEngine
from .logging import configure_logging
from .pipeline import AskPipeline
from .ratelimit import RateLimiter
from .redteam import RedteamRunner
from .services import Services
from .sweeper import Sweeper

REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
log = structlog.get_logger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get("x-request-id")
        request_id = (
            incoming if incoming and REQUEST_ID_RE.fullmatch(incoming) else uuid.uuid4().hex
        )
        request.state.request_id = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.monotonic()
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers["x-request-id"] = request_id
        if request.url.path not in {"/healthz", "/readyz"}:
            log.info(
                "http_request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=round((time.monotonic() - started) * 1000, 1),
            )
        return response


class BodyLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, *, max_bytes: int) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in {"POST", "PUT", "PATCH"}:
            return await call_next(request)
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                return _error_response(
                    request, 400, E_BAD_REQUEST, "content-length is not a number"
                )
            if declared > self.max_bytes:
                return _error_response(
                    request,
                    413,
                    E_PAYLOAD_TOO_LARGE,
                    f"request body exceeds {self.max_bytes} bytes",
                )
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > self.max_bytes:
                return _error_response(
                    request,
                    413,
                    E_PAYLOAD_TOO_LARGE,
                    f"request body exceeds {self.max_bytes} bytes",
                )
        request._body = bytes(body)
        return await call_next(request)


def _request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else ""


def _error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"code": code, "message": message, "request_id": _request_id(request)},
    )


def _broker_public_key(private_key: bytes) -> tuple[str, str]:
    key = X25519PrivateKey.from_private_bytes(private_key)
    public = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return (
        base64.b64encode(public).decode("ascii"),
        hashlib.sha256(public).hexdigest(),
    )


def create_app(
    settings: Settings | None = None,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    engine: AsyncEngine | None = None,
    chain: ChainProtocol | None = None,
    inference: InferenceProtocol | None = None,
    now: Callable[[], datetime] | None = None,
    start_background: bool = True,
) -> FastAPI:
    configured = settings or get_settings()
    configure_logging(configured.log_level)

    owns_engine = session_factory is None
    if session_factory is None:
        engine = create_engine(configured.database_url)
        session_factory = create_session_factory(engine)
    owns_chain = chain is None
    if chain is None:
        chain = ChainClient(configured)
    owns_inference = inference is None
    if inference is None:
        inference = NearAiInferenceEngine(configured)

    publisher = ActivityPublisher()
    limiter = RateLimiter()
    pipeline = AskPipeline(
        settings=configured,
        session_factory=session_factory,
        chain=chain,
        inference=inference,
        publisher=publisher,
        now=now,
    )
    sweeper = (
        Sweeper(
            session_factory=session_factory,
            chain=chain,
            publisher=publisher,
            interval_seconds=configured.sweeper_interval_seconds,
            ttl_seconds=600,
        )
        if start_background and configured.sweeper_enabled
        else None
    )
    public_key_b64, fingerprint = _broker_public_key(configured.broker_private_key)
    services = Services(
        settings=configured,
        engine=engine,
        session_factory=session_factory,
        chain=chain,
        inference=inference,
        publisher=publisher,
        limiter=limiter,
        pipeline=pipeline,
        redteam=RedteamRunner(pipeline, configured.nearai_model),
        sweeper=sweeper,
        broker_public_key_b64=public_key_b64,
        broker_fingerprint=fingerprint,
        owns_engine=owns_engine,
        owns_chain=owns_chain,
        owns_inference=owns_inference,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        task: asyncio.Task[None] | None = None
        if services.sweeper is not None:
            task = asyncio.create_task(services.sweeper.run_forever(), name="mnemos-sweeper")
        try:
            yield
        finally:
            if services.sweeper is not None:
                services.sweeper.stop()
            if task is not None:
                with contextlib.suppress(asyncio.TimeoutError, asyncio.CancelledError):
                    await asyncio.wait_for(task, timeout=5.0)
                if not task.done():
                    task.cancel()
            if services.owns_inference:
                await services.inference.close()
            if services.owns_chain:
                await services.chain.close()
            if services.owns_engine and services.engine is not None:
                await services.engine.dispose()

    app = FastAPI(
        title="Mnemos Broker",
        version="0.1.0",
        description=(
            "Scoped, metered memory access. The broker decrypts only the granted "
            "scope, verifies NEAR AI TEE responses, filters output, and settles a "
            "hash-only receipt on chain."
        ),
        lifespan=lifespan,
    )
    app.state.services = services

    app.add_middleware(BodyLimitMiddleware, max_bytes=configured.max_request_bytes)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=configured.allowed_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["content-type", "x-request-id", "authorization"],
        max_age=600,
    )

    @app.exception_handler(MnemosError)
    async def mnemos_error(request: Request, exc: MnemosError) -> JSONResponse:
        content: dict[str, Any] = {
            "code": exc.code,
            "message": exc.message,
            "request_id": _request_id(request),
        }
        if exc.details:
            content["details"] = exc.details
        return JSONResponse(status_code=exc.status_code, content=content)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [
            {
                "loc": [str(part) for part in error.get("loc", ())],
                "msg": str(error.get("msg", "invalid value")),
                "type": str(error.get("type", "value_error")),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "code": "E_VALIDATION",
                "message": "request validation failed",
                "request_id": _request_id(request),
                "details": {"fields": fields},
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = E_NOT_FOUND if exc.status_code == 404 else E_BAD_REQUEST
        message = exc.detail if isinstance(exc.detail, str) else "request failed"
        return _error_response(request, exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", path=request.url.path)
        return _error_response(
            request, 500, E_INTERNAL, "the broker could not complete this request"
        )

    for router in (
        auth.router,
        broker.router,
        vault.router,
        ask.router,
        activity.router,
        redteam.router,
    ):
        app.include_router(router, prefix="/v1")
    app.include_router(health.router)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "service": "mnemos-broker",
            "docs": "/docs",
            "health": "/healthz",
            "readiness": "/readyz",
        }

    return app
