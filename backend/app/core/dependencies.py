"""FastAPI dependencies — auth, permissions, config injection."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import Cookie, Depends, Header, HTTPException

from app.core.database import get_collection
from app.core.marketplace_config import MarketplaceConfig, get_marketplace_config
from app.modules.auth import api_keys
from app.modules.auth.api_keys import SCOPE_ADMIN
from app.engine.permission_engine import check_permission


def get_config() -> MarketplaceConfig:
    return get_marketplace_config()


def extract_bearer_token(authorization: str | None) -> str | None:
    """Pull the token out of an ``Authorization: Bearer <token>`` header, or None.

    This is the cross-origin credential path (GAP-1): a session cookie set by the API
    may not be sent back by browsers on genuinely cross-site requests (SameSite policy,
    third-party-cookie blocking), and non-browser callers (native apps, server-to-server
    integrations) have no cookie jar at all. Those callers authenticate by echoing the
    `access_token` returned from login/signup back in this header instead.
    """
    # Guard against FastAPI's unresolved `Header(None)` sentinel: dependencies are called
    # directly (not through request DI) in some unit tests, so `authorization` can arrive
    # as that sentinel object rather than a real `str | None`.
    if not isinstance(authorization, str) or not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


async def get_current_user_from_token(session_token: str | None) -> dict[str, Any]:
    """Resolve the current user from an explicit session token."""
    if not session_token:
        raise HTTPException(401, "Not authenticated")

    sessions = get_collection("sessions")
    session = await sessions.find_one({"token": session_token})
    if not session:
        raise HTTPException(401, "Invalid session")
    if _is_session_expired(session.get("expires_at")):
        # Best-effort cleanup of stale/invalid sessions to reduce repeated auth hits.
        if session.get("_id"):
            await sessions.delete_one({"_id": session["_id"]})
        raise HTTPException(401, "Session expired")

    users = get_collection("users")
    user = await users.find_one({"_id": session["user_id"]})
    if not user:
        raise HTTPException(401, "User not found")

    if user.get("is_active") is False:
        raise HTTPException(403, "Account deactivated")

    user["_id"] = str(user["_id"])
    return user


async def get_current_user_from_api_key(api_key: str | None) -> dict[str, Any]:
    """Resolve the current user from an ``X-API-Key`` header (GAP-1).

    A long-lived credential for callers that have no login session at all —
    a sponsor's backend integrating server-to-server. An invalid key raises
    rather than falling through to the cookie, so a wrong key never silently
    authenticates as whoever happens to be logged in in the same browser.
    """
    user = await api_keys.resolve_api_key(api_key or "")
    if not user:
        raise HTTPException(401, "Invalid API key")
    user["_id"] = str(user["_id"])
    return user


async def get_current_user(
    session_token: str = Cookie(None),
    authorization: str = Header(None),
    x_api_key: str = Header(None),
) -> dict[str, Any]:
    """Resolve the current user from an API key, an ``Authorization: Bearer`` header,
    or the session cookie (GAP-1), in that order of precedence.

    Explicit credentials win over the ambient cookie: a caller that sets a header is
    asserting that identity, e.g. to bypass a stale or absent cookie.
    Raises 401 if none resolves to a valid session.
    """
    if isinstance(x_api_key, str) and x_api_key:
        return await get_current_user_from_api_key(x_api_key)
    token = extract_bearer_token(authorization) or session_token
    return await get_current_user_from_token(token)


def _is_session_expired(expires_at: Any) -> bool:
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at)
        except ValueError:
            return True
    if not isinstance(expires_at, datetime):
        return True
    if expires_at.tzinfo is None:
        now_naive_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        return expires_at < now_naive_utc
    return expires_at.astimezone(timezone.utc) < datetime.now(timezone.utc)


async def get_optional_user(
    session_token: str = Cookie(None),
    authorization: str = Header(None),
    x_api_key: str = Header(None),
) -> dict[str, Any] | None:
    """Like get_current_user but returns None instead of raising."""
    if isinstance(x_api_key, str) and x_api_key:
        try:
            return await get_current_user_from_api_key(x_api_key)
        except HTTPException:
            return None
    token = extract_bearer_token(authorization) or session_token
    if not token:
        return None
    try:
        return await get_current_user_from_token(token)
    except HTTPException:
        return None


async def require_session_principal(
    session_token: str = Cookie(None),
    authorization: str = Header(None),
) -> dict[str, Any]:
    """Resolve the caller from a session cookie or bearer token only — never an API key.

    Guards credential management. If an API key could authenticate here, a stolen
    key could mint further keys, and revoking the original would not evict the
    attacker: leaked-and-containable becomes leaked-and-persistent. Key management
    therefore requires the interactive credential that a human controls.
    """
    token = extract_bearer_token(authorization) or session_token
    return await get_current_user_from_token(token)


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    # An admin's API key is for integration, not for administering the marketplace.
    # Without this, issuing a key to a sponsor hands over admin whenever the
    # issuing user happens to be an admin.
    if user.get("auth_method") == "api_key" and SCOPE_ADMIN not in (user.get("scopes") or []):
        raise HTTPException(403, "This API key does not carry the 'admin' scope")
    return user


def require_scope(scope: str):
    """Factory: require a scope when the caller is an API key.

    Session and bearer callers are unaffected — scopes describe what a *key* may
    do, not what a person may do; a person's authority is their role.
    """

    async def checker(user: dict = Depends(get_current_user)) -> dict:
        if user.get("auth_method") == "api_key" and scope not in (user.get("scopes") or []):
            raise HTTPException(403, f"This API key does not carry the '{scope}' scope")
        return user

    return checker


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
