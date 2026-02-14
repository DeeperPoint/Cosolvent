from __future__ import annotations

from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError
from app.core.marketplace_config import MarketplaceConfig
from app.core.security import hash_password, verify_password
from app.modules.auth import repository as repo


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

    user = await repo.create_user(
        email=email,
        password_hash=hash_password(password),
        participant_type=participant_type,
    )
    token = await repo.create_session(user["_id"])
    return _auth_response(user, token)


async def login(email: str, password: str) -> dict:
    user = await repo.find_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
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

    user = await repo.create_user(
        email=email,
        password_hash=hash_password(password),
        participant_type=None,
        role="admin",
    )
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
