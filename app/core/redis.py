"""Redis connection management."""

from __future__ import annotations

from arq.connections import ArqRedis, create_pool
from arq.connections import RedisSettings

from app.core.config import settings

_redis: ArqRedis | None = None


def _parse_redis_settings() -> RedisSettings:
    url = settings.redis_url
    # arq RedisSettings expects host/port
    if url.startswith("redis://"):
        url = url[len("redis://"):]
    host, _, port_str = url.partition(":")
    port = int(port_str) if port_str else 6379
    return RedisSettings(host=host or "localhost", port=port)


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
