"""Concrete services attached to the FastAPI application state."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from .activity import ActivityPublisher
from .chain import ChainProtocol
from .config import Settings
from .inference import InferenceProtocol
from .pipeline import AskPipeline
from .ratelimit import RateLimiter
from .redteam import RedteamRunner
from .sweeper import Sweeper


@dataclass
class Services:
    settings: Settings
    engine: AsyncEngine | None
    session_factory: async_sessionmaker[AsyncSession]
    chain: ChainProtocol
    inference: InferenceProtocol
    publisher: ActivityPublisher
    limiter: RateLimiter
    pipeline: AskPipeline
    redteam: RedteamRunner
    sweeper: Sweeper | None
    broker_public_key_b64: str
    broker_fingerprint: str
    owns_engine: bool
    owns_chain: bool
    owns_inference: bool
