from __future__ import annotations

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
    session_token: str


class UserResponse(BaseModel):
    user_id: str
    email: str
    participant_type: str | None = None
    role: str
    has_onboarded: bool
