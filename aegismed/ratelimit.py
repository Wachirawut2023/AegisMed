"""A minimal per-client rate limiter for the costly/mutating endpoints.

AegisMed runs as a single process (see Dockerfile — no --workers flag), so a
plain in-memory sliding-window counter is enough; no Redis or other shared
store is needed. This protects the endpoints that either cost real money
(each /api/diagnose can trigger up to 9 LLM calls) or grow disk state
unboundedly (saved cases, comments) from a single client hammering them.
"""

import time
from collections import defaultdict

from fastapi import HTTPException, Request

from . import config

_WINDOW_SECONDS = 60.0
# How often to sweep out buckets with no requests left in the window, so a
# long-running process doesn't accumulate one entry per distinct IP forever.
_SWEEP_INTERVAL_SECONDS = 300.0

_buckets: dict[str, list[float]] = defaultdict(list)
_last_sweep = 0.0


def _prune(timestamps: list[float], now: float) -> list[float]:
    return [t for t in timestamps if now - t < _WINDOW_SECONDS]


def _sweep_stale_buckets(now: float) -> None:
    global _last_sweep
    if now - _last_sweep < _SWEEP_INTERVAL_SECONDS:
        return
    _last_sweep = now
    for ip in [ip for ip, ts in _buckets.items() if not _prune(ts, now)]:
        del _buckets[ip]


async def enforce(request: Request) -> None:
    """FastAPI dependency: raise 429 once a client exceeds the per-minute budget.

    RATE_LIMIT_PER_MINUTE=0 disables rate limiting entirely (e.g. local dev).
    """
    limit = config.rate_limit_per_minute()
    if limit <= 0:
        return

    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    _sweep_stale_buckets(now)

    timestamps = _prune(_buckets[client_ip], now)
    if len(timestamps) >= limit:
        retry_after = max(1, int(_WINDOW_SECONDS - (now - timestamps[0])) + 1)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: max {limit} requests per {int(_WINDOW_SECONDS)}s. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )
    timestamps.append(now)
    _buckets[client_ip] = timestamps


def reset() -> None:
    """Test helper: clear all tracked buckets between tests."""
    global _last_sweep
    _buckets.clear()
    _last_sweep = 0.0
