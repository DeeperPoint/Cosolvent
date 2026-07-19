"""Background task: acknowledgment-window reminder sweep for deal story versions.

Scheduled via an ARQ cron in ``app.workers.settings`` (hourly); the actual cadence (which
day-thresholds fire) is per-vertical config (``story_progression.reminder_cadence_days``).
"""

from __future__ import annotations

import logging

from app.core.marketplace_config import get_marketplace_config

logger = logging.getLogger("cosolvent.worker.deal_reminders")


async def deal_reminder_sweep(ctx: dict) -> dict:
    from app.modules.deals import service

    try:
        result = await service.run_reminder_sweep(get_marketplace_config())
        logger.info("deal reminder sweep: %s", result)
        return result
    except Exception:
        logger.exception("deal reminder sweep failed")
        return {"deals_scanned": 0, "reminders_sent": 0}
