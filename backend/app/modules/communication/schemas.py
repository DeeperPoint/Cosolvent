from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer


class CreateConversationRequest(BaseModel):
    receiver_user_id: str
    initial_message: str | None = None


class SendMessageRequest(BaseModel):
    content: str
    content_type: str = "text"  # text | image | video | audio | file


class EditMessageRequest(BaseModel):
    content: str


class ShareAssetsRequest(BaseModel):
    asset_ids: list[str]


class ConversationResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    participants: list[dict[str, Any]]
    initiator_id: str
    rule_key: str
    status: str
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None

    @field_serializer("created_at", "updated_at")
    def _iso(self, v: datetime | str | None) -> str | None:
        if v is None or isinstance(v, str):
            return v
        return v.isoformat()


class MessageResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    conversation_id: str
    sender_id: str
    content: str
    content_type: str
    edited: bool = False
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None

    @field_serializer("created_at", "updated_at")
    def _iso(self, v: datetime | str | None) -> str | None:
        if v is None or isinstance(v, str):
            return v
        return v.isoformat()
