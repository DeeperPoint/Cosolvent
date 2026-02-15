"""arq worker settings."""

from __future__ import annotations

from arq.connections import RedisSettings

from app.core.config import settings
from app.core.database import close_db, connect_db
from app.core.marketplace_config import load_marketplace_config, set_marketplace_config


def _parse_redis_settings() -> RedisSettings:
    url = settings.redis_url
    if url.startswith("redis://"):
        url = url[len("redis://"):]
    host, _, port_str = url.partition(":")
    port = int(port_str) if port_str else 6379
    return RedisSettings(host=host or "localhost", port=port)


async def _worker_startup(ctx: dict) -> None:
    config = load_marketplace_config(settings.marketplace_config_path)
    set_marketplace_config(config)
    await connect_db()


async def _worker_shutdown(ctx: dict) -> None:
    await close_db()


class WorkerSettings:
    redis_settings = _parse_redis_settings()
    functions = [
        "app.workers.document_indexing.process_document_task",
        "app.workers.profile_indexing.index_profile_task",
        "app.workers.email_sender.send_email_task",
    ]
    on_startup = _worker_startup
    on_shutdown = _worker_shutdown
    max_jobs = 10
