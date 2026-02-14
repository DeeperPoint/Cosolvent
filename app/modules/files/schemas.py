from __future__ import annotations

from pydantic import BaseModel


class FileResponse(BaseModel):
    id: str
    user_id: str
    profile_id: str | None = None
    filename: str
    url: str
    content_type: str
    privacy: str
    category: str
    created_at: str | None = None


class PrivateAssetResponse(BaseModel):
    id: str
    user_id: str
    profile_id: str
    participant_type: str
    filename: str
    url: str
    content_type: str
    created_at: str | None = None
