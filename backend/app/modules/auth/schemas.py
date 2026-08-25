from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    participant_type: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class BootstrapRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    user_id: str
    email: str
    participant_type: str | None = None
    role: str
    has_onboarded: bool
    # Bearer credential for cross-origin/native/server-to-server callers (GAP-1) — send
    # back as `Authorization: Bearer <access_token>`. Only populated when the caller
    # opts in with `X-Auth-Mode: bearer`; otherwise it is absent, so a same-origin
    # browser client never receives the session token in a JS-readable form.
    access_token: str | None = None


class UserResponse(BaseModel):
    user_id: str
    email: str
    participant_type: str | None = None
    role: str
    has_onboarded: bool


class DemoPersonaRequest(BaseModel):
    participant_type: str


class PersonaSummary(BaseModel):
    profile_id: str
    participant_type: str
    fields: dict[str, Any]


class DemoPersonaResponse(AuthResponse):
    # The synthetic profile the caller is now logged in as — the demo-ui role picker
    # (MarketForge Phase 6a) shows this instead of asking the visitor to fill anything in.
    persona: PersonaSummary


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Label to identify this key")
    scopes: list[str] | None = Field(
        None, description="Scopes for this key; defaults to read+write. 'admin' is never implicit."
    )
    expires_in_days: int | None = Field(
        None, ge=1, le=3650, description="Optional lifetime. Omit for a non-expiring key."
    )


class ApiKeyCreatedResponse(BaseModel):
    """The only response that ever carries the key itself."""

    id: str
    name: str
    api_key: str = Field(..., description="Shown once — it cannot be retrieved again")
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None
    created_at: datetime | None = None


class ApiKeyResponse(BaseModel):
    id: str
    name: str | None = None
    key_hint: str | None = Field(None, description="Last 4 characters, to identify a key")
    scopes: list[str] = Field(default_factory=list)
    revoked: bool = False
    expired: bool = False
    expires_at: datetime | None = None
    created_at: datetime | None = None
    last_used_at: datetime | None = None
