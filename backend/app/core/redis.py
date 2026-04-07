"""Redis connection management."""

from __future__ import annotations

from urllib.parse import urlparse

from arq.connections import ArqRedis, create_pool
from arq.connections import RedisSettings

from app.core.config import settings

_redis: ArqRedis | None = None


def parse_redis_settings(url: str) -> RedisSettings:
    normalized = url.strip()
    if not normalized:
        return RedisSettings(host="localhost", port=6379)

    if "://" not in normalized:
        normalized = f"redis://{normalized}"

    parsed = urlparse(normalized)
    if parsed.scheme not in {"redis", "rediss"}:
        raise ValueError(f"Unsupported Redis URL scheme: {parsed.scheme}")

    database = 0
    if parsed.path and parsed.path != "/":
        database = int(parsed.path.lstrip("/"))

    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=database,
        username=parsed.username,
        password=parsed.password,
        ssl=parsed.scheme == "rediss",
    )


def _parse_redis_settings() -> RedisSettings:
    return parse_redis_settings(settings.redis_url)


async def connect_redis() -> None:
    global _redis
    _redis = await create_pool(_parse_redis_settings())


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
    _redis = None


def get_redis() -> ArqRedis:
    if _redis is None:
        raise RuntimeError("Redis not connected")
    return _redis
