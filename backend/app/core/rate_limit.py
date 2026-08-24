"""Fixed-window rate limiting for authentication endpoints.

CORS is a *browser* control — it does nothing about `curl`. An origin allowlist
therefore gives zero protection against scripted credential stuffing, which is
exactly what becomes attractive once an API is deliberately reachable
cross-origin. Login needs its own throttle.

Backed by Redis so the limit holds across workers; falls back to an in-process
counter when Redis is unavailable, which keeps the protection meaningful in
single-node and test runs rather than silently disabling it.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict

logger = logging.getLogger("cosolvent.rate_limit")

# Per-IP: blunt, catches a single host spraying many accounts.
LOGIN_IP_LIMIT = 20
LOGIN_IP_WINDOW_SECONDS = 300

# Per-account: catches a distributed attack converging on one valuable account,
# which the IP limit alone would miss.
LOGIN_ACCOUNT_LIMIT = 5
LOGIN_ACCOUNT_WINDOW_SECONDS = 300

# name -> (window_start_epoch, count)
_memory_windows: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))


def _now() -> float:
    return time.monotonic()


async def _hit_redis(key: str, window_seconds: int) -> int | None:
    """Increment and return the count for this window, or None if Redis is unusable."""
    try:
        from app.core.redis import get_redis

        # Raises RuntimeError when Redis was never connected (tests, single-node
        # runs without a queue); the except below falls back to the in-process
        # counter rather than dropping the protection entirely.
        redis = get_redis()
        count = await redis.incr(key)
        if count == 1:
            # Expire the whole window on first hit — a fixed window, so the
            # counter resets wholesale rather than sliding.
            await redis.expire(key, window_seconds)
        return int(count)
    except Exception:  # noqa: BLE001 - fall back rather than fail the request
        return None


def _hit_memory(key: str, window_seconds: int) -> int:
    start, count = _memory_windows[key]
    now = _now()
    if start == 0.0 or now - start >= window_seconds:
        _memory_windows[key] = (now, 1)
        return 1
    _memory_windows[key] = (start, count + 1)
    return count + 1


async def hit(key: str, window_seconds: int) -> int:
    """Register one attempt against `key`; return the count within the window."""
    count = await _hit_redis(f"ratelimit:{key}", window_seconds)
    if count is not None:
        return count
    return _hit_memory(key, window_seconds)


async def check_login_attempt(ip: str | None, email: str | None) -> int | None:
    """Return seconds to wait if this login attempt should be refused, else None.

    Counts every attempt, successful or not: a limiter that only counts failures
    lets an attacker with a valid credential enumerate freely.
    """
    if ip:
        count = await hit(f"login:ip:{ip}", LOGIN_IP_WINDOW_SECONDS)
        if count > LOGIN_IP_LIMIT:
            logger.warning("Login rate limit hit for IP %s (%d attempts)", ip, count)
            return LOGIN_IP_WINDOW_SECONDS

    if email:
        key = email.strip().lower()
        count = await hit(f"login:account:{key}", LOGIN_ACCOUNT_WINDOW_SECONDS)
        if count > LOGIN_ACCOUNT_LIMIT:
            logger.warning("Login rate limit hit for account %s (%d attempts)", key, count)
            return LOGIN_ACCOUNT_WINDOW_SECONDS

    return None


def reset() -> None:
    """Clear in-process counters. For tests."""
    _memory_windows.clear()
