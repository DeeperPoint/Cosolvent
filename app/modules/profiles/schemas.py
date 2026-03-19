from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr


class ProfileRegisterPendingResponse(BaseModel):
    """Public apply flow: no account yet — waiting for admin approval."""

    status: Literal["pending_review"]
    application_id: str


class ProfileRegisterRequest(BaseModel):
    """With session: create/update draft. Without session: submit email + fields as a pending application only."""

    email: EmailStr | None = None
    fields: dict | None = None


class RegisterRequest(BaseModel):
    """Minimal registration — creates user + empty draft."""
    ...


class DraftUpdateRequest(BaseModel):
    """Update draft fields — validated dynamically against config schema."""
    fields: dict


class ProfileResponse(BaseModel):
    id: str
    user_id: str
    participant_type: str
    status: str
    fields: dict
    ai_profile: str | None = None
    ai_profile_draft: str | None = None
    ai_profile_status: str = "none"
    ai_profile_updated_at: str | None = None
    completeness: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class ApplicationResponse(BaseModel):
    id: str
    user_id: str
    participant_type: str
    draft_id: str
    status: str
    admin_feedback: str | None = None
    created_at: str | None = None


class AdminFeedbackRequest(BaseModel):
    feedback: str = ""


class AIProfileActionResponse(BaseModel):
    status: Literal["generated", "approved", "rejected"]
    profile_id: str
    ai_profile: str | None = None
    ai_profile_draft: str | None = None
    ai_profile_status: str = "none"
    ai_profile_updated_at: str | None = None
