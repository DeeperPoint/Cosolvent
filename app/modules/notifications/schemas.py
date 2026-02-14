from __future__ import annotations

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    type: str
    data: dict
    is_read: bool
    created_at: str | None = None
