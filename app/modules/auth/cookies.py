"""HttpOnly session cookie helpers (shared by auth and profile registration)."""

from __future__ import annotations

from fastapi import Response

from app.core.config import settings


def set_session_cookie(response: Response, token: str) -> None:
    max_age_seconds = settings.session_ttl_hours * 60 * 60
    response.set_cookie(
        "session_token",
        token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=max_age_seconds,
    )
