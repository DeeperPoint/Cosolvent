"""FastAPI dependencies — auth, permissions, config injection."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import Cookie, Depends, HTTPException

from app.core.database import get_collection
from app.core.marketplace_config import MarketplaceConfig, get_marketplace_config
from app.engine.permission_engine import check_permission


def get_config() -> MarketplaceConfig:
    return get_marketplace_config()


async def get_current_user(session_token: str = Cookie(None)) -> dict[str, Any]:
    """Resolve the current user from session cookie. Raises 401 if invalid."""
    if not session_token:
        raise HTTPException(401, "Not authenticated")

    sessions = get_collection("sessions")
    session = await sessions.find_one({"token": session_token})
    if not session:
        raise HTTPException(401, "Invalid session")
    if session.get("expires_at") and session["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(401, "Session expired")

    users = get_collection("users")
    user = await users.find_one({"_id": session["user_id"]})
    if not user:
        raise HTTPException(401, "User not found")

    if user.get("is_active") is False:
        raise HTTPException(403, "Account deactivated")

    user["_id"] = str(user["_id"])
    return user


async def get_optional_user(session_token: str = Cookie(None)) -> dict[str, Any] | None:
    """Like get_current_user but returns None instead of raising."""
    if not session_token:
        return None
    try:
        return await get_current_user(session_token)
    except HTTPException:
        return None


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    return user


def require_permission(permission: str):
    """Factory that returns a dependency checking a specific permission."""

    async def checker(
        user: dict = Depends(get_current_user),
        config: MarketplaceConfig = Depends(get_config),
    ) -> dict:
        if user.get("role") == "admin":
            return user
        if not check_permission(config, user.get("participant_type", ""), permission):
            raise HTTPException(403, f"Missing permission: {permission}")
        return user

    return checker


def require_type_slug(config: MarketplaceConfig = Depends(get_config)):
    """Returns a validator that checks a type_slug path param is valid."""

    def validate(type_slug: str) -> str:
        if config.get_type(type_slug) is None:
            raise HTTPException(404, f"Unknown participant type: {type_slug}")
        return type_slug

    return validate
