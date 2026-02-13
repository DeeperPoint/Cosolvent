"""arq worker settings."""

from __future__ import annotations

from arq.connections import RedisSettings

from app.core.config import settings


def _parse_redis_settings() -> RedisSettings:
    url = settings.redis_url
    if url.startswith("redis://"):
        url = url[len("redis://"):]
    host, _, port_str = url.partition(":")
    port = int(port_str) if port_str else 6379
    return RedisSettings(host=host or "localhost", port=port)


class WorkerSettings:
    redis_settings = _parse_redis_settings()
    functions = [
        "app.workers.document_indexing.process_document_task",
        "app.workers.profile_indexing.index_profile_task",
        "app.workers.email_sender.send_email_task",
    ]
    max_jobs = 10
