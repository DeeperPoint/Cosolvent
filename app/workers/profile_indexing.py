"""Background task: index profiles to Postgres vectors."""

from __future__ import annotations

import logging

logger = logging.getLogger("cosolvent.worker.profileindex")


async def index_profile_task(ctx: dict, profile_id: str) -> None:
    from app.core.marketplace_config import get_marketplace_config
    from app.modules.profiles.repository import get_profile_by_id
    from app.modules.discovery.indexer import index_profile

    logger.info("Indexing profile %s", profile_id)
    profile = await get_profile_by_id(profile_id)
    if profile:
        config = get_marketplace_config()
        await index_profile(profile, config)
