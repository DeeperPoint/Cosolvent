from __future__ import annotations

from app.core.exceptions import NotFoundError
from app.modules.notifications import repository as repo


async def create_notification(user_id: str, notification_type: str, data: dict) -> dict:
    notif = await repo.create_notification(user_id, notification_type, data)
    return _response(notif)


async def list_notifications(user_id: str, skip: int = 0, limit: int = 50) -> list[dict]:
    notifs = await repo.list_notifications(user_id, skip, limit)
    return [_response(n) for n in notifs]


async def mark_read(notification_id: str) -> dict:
    notif = await repo.mark_read(notification_id)
    if not notif:
        raise NotFoundError("Notification not found")
    return _response(notif)


def _response(notif: dict) -> dict:
    return {
        "id": str(notif["_id"]),
        "user_id": notif["user_id"],
        "type": notif["type"],
        "data": notif["data"],
        "is_read": notif["is_read"],
        "created_at": str(notif.get("created_at", "")),
    }
