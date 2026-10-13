import asyncio
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from sentinel.api import InMemoryRateLimiter


@pytest.mark.asyncio
async def test_allows_requests_within_limit() -> None:
    limiter = InMemoryRateLimiter()

    await limiter.check(
        api_key="test-key",
        endpoint="POST:/incidents",
        max_requests=2,
    )
    await limiter.check(
        api_key="test-key",
        endpoint="POST:/incidents",
        max_requests=2,
    )


@pytest.mark.asyncio
async def test_rejects_requests_over_limit() -> None:
    limiter = InMemoryRateLimiter()

    await limiter.check(
        api_key="test-key",
        endpoint="POST:/incidents",
        max_requests=1,
    )

    with pytest.raises(HTTPException) as exc_info:
        await limiter.check(
            api_key="test-key",
            endpoint="POST:/incidents",
            max_requests=1,
        )

    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers
    assert int(exc_info.value.headers["Retry-After"]) >= 1


@pytest.mark.asyncio
async def test_limits_are_isolated_by_api_key() -> None:
    limiter = InMemoryRateLimiter()

    await limiter.check(
        api_key="key-one",
        endpoint="POST:/incidents",
        max_requests=1,
    )

    # A different API key gets its own bucket.
    await limiter.check(
        api_key="key-two",
        endpoint="POST:/incidents",
        max_requests=1,
    )


@pytest.mark.asyncio
async def test_limits_are_isolated_by_endpoint() -> None:
    limiter = InMemoryRateLimiter()

    await limiter.check(
        api_key="test-key",
        endpoint="POST:/incidents",
        max_requests=1,
    )

    # The same API key has an independent bucket per endpoint.
    await limiter.check(
        api_key="test-key",
        endpoint="POST:/incidents/{incident_id}/investigate",
        max_requests=1,
    )


@pytest.mark.asyncio
async def test_allows_request_after_window_expires() -> None:
    limiter = InMemoryRateLimiter()

    with patch("sentinel.api.monotonic", side_effect=[100.0, 161.0]):
        await limiter.check(
            api_key="test-key",
            endpoint="POST:/incidents",
            max_requests=1,
            window_seconds=60,
        )

        # The first request is now outside the 60-second window.
        await limiter.check(
            api_key="test-key",
            endpoint="POST:/incidents",
            max_requests=1,
            window_seconds=60,
        )


@pytest.mark.asyncio
async def test_concurrent_requests_respect_limit() -> None:
    limiter = InMemoryRateLimiter()

    async def make_request() -> bool:
        try:
            await limiter.check(
                api_key="test-key",
                endpoint="POST:/incidents",
                max_requests=5,
            )
            return True
        except HTTPException as exc:
            if exc.status_code == 429:
                return False
            raise

    results = await asyncio.gather(*(make_request() for _ in range(20)))

    assert sum(results) == 5
