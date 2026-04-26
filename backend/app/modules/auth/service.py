from __future__ import annotations

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


async def change_password(user: dict, current_password: str, new_password: str) -> None:
    """Update the caller's password.

    Verifies ``current_password`` against the stored hash, then writes a new
    bcrypt hash. Raises ``UnauthorizedError`` if the current password is wrong;
    raises ``ValueError`` for invalid new passwords (caller maps to 422).
    """
    if not verify_password(current_password, user.get("password_hash")):
        raise UnauthorizedError("Current password is incorrect")
    if not new_password or len(new_password) < 8:
        raise ValueError("New password must be at least 8 characters")
    if new_password == current_password:
        raise ValueError("New password must differ from the current one")

    from app.core.database import get_collection
    await get_collection("users").update_one(
        {"_id": user["_id"]},
        {"$set": {"password_hash": hash_password(new_password)}},
    )
