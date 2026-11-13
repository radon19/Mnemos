from __future__ import annotations

from mnemos_broker.ratelimit import RateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


async def test_capacity_and_refill() -> None:
    clock = FakeClock()
    limiter = RateLimiter(clock=clock)
    assert await limiter.allow("a", capacity=2, per_seconds=60)
    assert await limiter.allow("a", capacity=2, per_seconds=60)
    assert not await limiter.allow("a", capacity=2, per_seconds=60)
    clock.advance(30)
    assert await limiter.allow("a", capacity=2, per_seconds=60)
    assert not await limiter.allow("a", capacity=2, per_seconds=60)
    clock.advance(60)
    assert await limiter.allow("a", capacity=2, per_seconds=60)
    assert await limiter.allow("a", capacity=2, per_seconds=60)


async def test_keys_are_independent() -> None:
    limiter = RateLimiter(clock=FakeClock())
    assert await limiter.allow("a", capacity=1, per_seconds=60)
    assert not await limiter.allow("a", capacity=1, per_seconds=60)
    assert await limiter.allow("b", capacity=1, per_seconds=60)


async def test_reset_clears_buckets() -> None:
    clock = FakeClock()
    limiter = RateLimiter(clock=clock)
    assert await limiter.allow("a", capacity=1, per_seconds=60)
    assert not await limiter.allow("a", capacity=1, per_seconds=60)
    limiter.reset()
    assert await limiter.allow("a", capacity=1, per_seconds=60)
