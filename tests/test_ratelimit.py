"""Unit tests for the per-client rate limiter (aegismed/ratelimit.py).

`enforce()` only reads `request.client.host`, so a tiny stand-in is enough —
no need for a real Starlette Request/ASGI scope.
"""

import time

import pytest
from fastapi import HTTPException

from aegismed import ratelimit

pytestmark = pytest.mark.anyio


class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    def __init__(self, host="1.2.3.4"):
        self.client = _FakeClient(host)


@pytest.fixture(autouse=True)
def _reset_buckets():
    ratelimit.reset()
    yield
    ratelimit.reset()


async def test_enforce_allows_requests_within_limit(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")
    request = _FakeRequest()
    for _ in range(3):
        await ratelimit.enforce(request)  # must not raise


async def test_enforce_blocks_once_limit_exceeded(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")
    request = _FakeRequest()
    for _ in range(3):
        await ratelimit.enforce(request)

    with pytest.raises(HTTPException) as exc_info:
        await ratelimit.enforce(request)

    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers


async def test_enforce_tracks_clients_independently(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    a, b = _FakeRequest("1.1.1.1"), _FakeRequest("2.2.2.2")

    await ratelimit.enforce(a)  # uses up 1.1.1.1's budget
    await ratelimit.enforce(b)  # 2.2.2.2 is unaffected

    with pytest.raises(HTTPException):
        await ratelimit.enforce(a)


async def test_enforce_zero_limit_disables_rate_limiting(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "0")
    request = _FakeRequest()
    for _ in range(50):
        await ratelimit.enforce(request)  # must never raise


async def test_enforce_missing_client_falls_back_to_unknown_bucket(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    request = _FakeRequest()
    request.client = None  # e.g. some ASGI test transports omit it

    await ratelimit.enforce(request)  # first request from "unknown" succeeds
    with pytest.raises(HTTPException):
        await ratelimit.enforce(request)


async def test_sweep_stale_buckets_drops_expired_entries(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "5")
    request = _FakeRequest("9.9.9.9")
    await ratelimit.enforce(request)
    assert "9.9.9.9" in ratelimit._buckets

    # Force the window to have fully elapsed and the sweep interval to be due.
    future = time.monotonic() + ratelimit._WINDOW_SECONDS + ratelimit._SWEEP_INTERVAL_SECONDS + 1
    ratelimit._sweep_stale_buckets(future)
    assert "9.9.9.9" not in ratelimit._buckets
