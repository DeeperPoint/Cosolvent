"""arq worker settings."""

from __future__ import annotations

from arq import cron
from arq.connections import RedisSettings

from app.core.config import settings
from app.core.database import close_db, connect_db
from app.core.marketplace_config import load_marketplace_config, set_marketplace_config
from app.core.redis import parse_redis_settings
from app.workers.deal_reminders import deal_reminder_sweep


def _parse_redis_settings() -> RedisSettings:
    return parse_redis_settings(settings.redis_url)


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
        deal_reminder_sweep,
    ]
    # Hourly acknowledgment-reminder sweep; per-vertical cadence decides which thresholds fire.
    cron_jobs = [cron(deal_reminder_sweep, minute=0)]
    on_startup = _worker_startup
    on_shutdown = _worker_shutdown
    max_jobs = 10
