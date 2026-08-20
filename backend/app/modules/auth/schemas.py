from __future__ import annotations

from typing import Any

from pydantic import BaseModel, EmailStr


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
    # back as `Authorization: Bearer <access_token>`. Same-origin browser clients can
    # ignore this and rely on the HttpOnly session cookie set alongside it.
    access_token: str


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
