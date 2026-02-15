from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from bson import ObjectId

from app.core.database import get_collection
from app.core.config import settings
from app.core.security import generate_session_token


async def find_user_by_email(email: str) -> dict | None:
    return await get_collection("users").find_one({"email": email})


async def find_user_by_id(user_id: str) -> dict | None:
    return await get_collection("users").find_one({"_id": ObjectId(user_id)})


async def create_user(
    email: str,
    password_hash: str,
    participant_type: str | None,
    role: str = "user",
) -> dict[str, Any]:
    doc = {
        "email": email,
        "password_hash": password_hash,
        "participant_type": participant_type,
        "role": role,
        "is_active": True,
        "has_onboarded": False,
        "created_at": datetime.now(timezone.utc),
    }
    result = await get_collection("users").insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def create_session(user_id: ObjectId) -> str:
    token = generate_session_token()
    await get_collection("sessions").insert_one({
        "token": token,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours),
    })
    return token


async def delete_session(token: str) -> None:
    await get_collection("sessions").delete_one({"token": token})


async def count_admins() -> int:
    return await get_collection("users").count_documents({"role": "admin"})
