from __future__ import annotations

from typing import Any

from app.core.marketplace_config import MarketplaceConfig
from app.modules.admin import repository as repo
from app.modules.profiles import repository as profiles_repo
from app.modules.profiles import service as profiles_service


async def get_dashboard(config: MarketplaceConfig) -> dict[str, Any]:
    stats = await repo.get_dashboard_stats()
    stats["marketplace"] = {
        "name": config.marketplace.name,
        "industry": config.marketplace.industry,
        "participant_types": config.type_slugs(),
    }
    return stats


async def list_users(skip: int = 0, limit: int = 50) -> list[dict]:
    users = await repo.list_users(skip, limit)
    return [_serialize(u) for u in users]


async def list_applications(status: str | None = None) -> list[dict]:
    apps = await profiles_repo.list_applications(status)
    return [_serialize(a) for a in apps]


async def approve_application(app_id: str, config: MarketplaceConfig) -> dict[str, Any]:
    return await profiles_service.approve_application(app_id, config)


async def reject_application(
    app_id: str, feedback: str | None = None
) -> dict[str, Any]:
    return await profiles_service.reject_application(app_id, feedback)


async def get_config_summary(config: MarketplaceConfig) -> dict[str, Any]:
    return {
        "marketplace": config.marketplace.model_dump(),
        "participant_types": [pt.model_dump() for pt in config.participant_types],
        "communication_rules": [r.model_dump() for r in config.communication.conversation_rules],
        "discovery": config.discovery.model_dump(),
    }


def _serialize(doc: dict) -> dict:
    if doc is None:
        return {}
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc
