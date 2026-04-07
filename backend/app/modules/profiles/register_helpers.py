"""Shared checks for profile registration routes."""

from __future__ import annotations

from fastapi import HTTPException


def ensure_role_matches_route(user: dict, role_slug: str) -> None:
    """Non-admins must have participant_type matching the registration route."""
    if user.get("role") == "admin":
        return
    participant_type = user.get("participant_type")
    if participant_type != role_slug:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Profile registration for '{role_slug}' does not match "
                f"your participant type '{participant_type}'"
            ),
        )
