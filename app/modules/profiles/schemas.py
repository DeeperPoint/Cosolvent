from __future__ import annotations

from pydantic import BaseModel


class RegisterRequest(BaseModel):
    """Minimal registration — creates user + empty draft."""
    pass


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
