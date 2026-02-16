from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

FilePrivacy = Literal["public", "private"]


class FileResponse(BaseModel):
    id: str
    user_id: str
    profile_id: str | None = None
    filename: str
    url: str
    s3_key: str | None = None
    size_bytes: int | None = None
    content_type: str
    privacy: FilePrivacy
    category: str
    created_at: str | None = None


class PrivateAssetResponse(BaseModel):
    id: str
    user_id: str
    profile_id: str
    participant_type: str
    filename: str
    url: str
    s3_key: str | None = None
    size_bytes: int | None = None
    content_type: str
    created_at: str | None = None
