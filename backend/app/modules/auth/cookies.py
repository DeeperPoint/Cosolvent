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
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        max_age=max_age_seconds,
    )


def clear_session_cookie(response: Response) -> None:
    """Delete the session cookie with attributes matching how it was set — a mismatched
    SameSite/Secure on delete leaves the original cookie stranded in the browser."""
    response.delete_cookie(
        "session_token",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite=settings.session_cookie_samesite,
    )
