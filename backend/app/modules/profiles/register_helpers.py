"""Shared checks for profile registration routes."""

from __future__ import annotations

from fastapi import HTTPException


def ensure_role_matches_route(user: dict, role_slug: str) -> None:
    """Authenticated registration requires a concrete participant_type that matches route."""
    if user.get("role") == "admin":
        raise HTTPException(
            status_code=403,
            detail=(
                "Admin accounts cannot submit participant registration via authenticated flow. "
                "Sign out and submit as an anonymous application instead."
            ),
        )
    participant_type = user.get("participant_type")
    if not participant_type:
        raise HTTPException(
            status_code=403,
            detail=(
                "Authenticated account has no participant type. "
                "Sign out and submit as an anonymous application instead."
            ),
        )
    if participant_type != role_slug:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Profile registration for '{role_slug}' does not match "
                f"your participant type '{participant_type}'"
            ),
        )
