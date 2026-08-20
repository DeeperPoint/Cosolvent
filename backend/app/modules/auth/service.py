from __future__ import annotations

import random

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError
from app.core.marketplace_config import MarketplaceConfig
from app.core.security import hash_password, verify_password
from app.modules.auth import repository as repo

_BOOTSTRAP_MARKER = "primary-admin"


async def signup(
    email: str,
    password: str,
    participant_type: str,
    config: MarketplaceConfig,
) -> dict:
    # Validate participant type against config
    if config.get_type(participant_type) is None:
        raise NotFoundError(f"Unknown participant type: {participant_type}")

    existing = await repo.find_user_by_email(email)
    if existing:
        raise ConflictError("Email already registered")

    try:
        user = await repo.create_user(
            email=email,
            password_hash=hash_password(password),
            participant_type=participant_type,
        )
    except IntegrityError as exc:
        if _is_unique_violation(exc, "uq_users_email"):
            raise ConflictError("Email already registered") from exc
        raise

    token = await repo.create_session(user["_id"])
    return _auth_response(user, token)


async def login(email: str, password: str) -> dict:
    user = await repo.find_user_by_email(email)
    if not user:
        raise UnauthorizedError("Invalid email or password")
    if not user.get("password_hash"):
        raise UnauthorizedError(
            "No password set for this account yet. Use the credentials from your approval email when ready."
        )
    if not verify_password(password, user.get("password_hash")):
        raise UnauthorizedError("Invalid email or password")

    token = await repo.create_session(user["_id"])
    return _auth_response(user, token)


async def logout(token: str) -> None:
    await repo.delete_session(token)


async def verify(user: dict) -> dict:
    return {
        "user_id": str(user["_id"]),
        "email": user["email"],
        "participant_type": user.get("participant_type"),
        "role": user.get("role", "user"),
        "has_onboarded": user.get("has_onboarded", False),
    }


async def bootstrap_admin(email: str, password: str) -> dict:
    count = await repo.count_admins()
    if count > 0:
        raise ConflictError("Admin already exists")

    try:
        user = await repo.create_user(
            email=email,
            password_hash=hash_password(password),
            participant_type=None,
            role="admin",
            bootstrap_marker=_BOOTSTRAP_MARKER,
        )
    except IntegrityError as exc:
        if _is_unique_violation(exc, "uq_users_bootstrap_marker"):
            raise ConflictError("Admin already exists") from exc
        if _is_unique_violation(exc, "uq_users_email"):
            raise ConflictError("Email already registered") from exc
        raise

    user["has_onboarded"] = True
    token = await repo.create_session(user["_id"])
    return _auth_response(user, token)


async def assign_demo_persona(participant_type: str, config: MarketplaceConfig) -> dict:
    """Log the caller in as a random synthetic participant of ``participant_type`` —
    the persona-assignment mechanic for a public demo instance (CONVERGENCE.md Phase
    6a: "the system randomly selects one synthetic participant of the chosen type and
    logs the visitor in as that persona"). Only ``is_synthetic`` profiles are ever
    eligible — never a real participant — and the router gates this to
    ``DEMO_MODE != "off"``: an unauthenticated "log me in as anyone" is only
    acceptable when every account it can reach is already known-synthetic.
    """
    if config.get_type(participant_type) is None:
        raise NotFoundError(f"Unknown participant type: {participant_type}")

    from app.modules.profiles import repository as profiles_repo

    candidates = await profiles_repo.list_profiles(participant_type, status="active", limit=500)
    synthetic = [p for p in candidates if p.get("is_synthetic")]
    if not synthetic:
        raise NotFoundError(
            f"No synthetic {participant_type} personas available — seed demo data first"
        )

    profile = random.choice(synthetic)
    user = await repo.find_user_by_id(profile["user_id"])
    if not user:
        raise NotFoundError("Persona's user account not found")

    token = await repo.create_session(user["_id"])
    result = _auth_response(user, token)
    result["persona"] = {
        "profile_id": str(profile.get("_id") or profile.get("id") or ""),
        "participant_type": participant_type,
        "fields": profile.get("fields", {}) or {},
    }
    return result


def _auth_response(user: dict, token: str) -> dict:
    return {
        "user_id": str(user["_id"]),
        "email": user["email"],
        "participant_type": user.get("participant_type"),
        "role": user.get("role", "user"),
        "has_onboarded": user.get("has_onboarded", False),
        "session_token": token,
    }


def _is_unique_violation(exc: IntegrityError, constraint_name: str) -> bool:
    message = str(getattr(exc, "orig", exc))
    return constraint_name in message
