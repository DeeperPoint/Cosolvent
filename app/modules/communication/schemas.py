from __future__ import annotations

from pydantic import BaseModel


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
    id: str
    participants: list[dict]
    initiator_id: str
    rule_key: str
    status: str
    created_at: str | None = None
    updated_at: str | None = None


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    content: str
    content_type: str
    edited: bool = False
    created_at: str | None = None
    updated_at: str | None = None
