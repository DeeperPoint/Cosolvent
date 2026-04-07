from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


from app.core.database import get_collection


import logging
logger = logging.getLogger("cosolvent")

# ── Drafts ────────────────────────────────────────────────────────────────

async def get_draft(user_id: str) -> dict | None:
    return await get_collection("drafts").find_one({"user_id": user_id})


async def upsert_draft(user_id: str, participant_type: str, fields: dict) -> dict:
    now = datetime.now(timezone.utc)
    doc = {
        "user_id": user_id,
        "participant_type": participant_type,
        "status": "draft",
        "fields": fields,
        "updated_at": now,
    }
    result = await get_collection("drafts").find_one_and_update(
        {"user_id": user_id},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
        return_document=True,
    )
    return result


async def delete_draft(user_id: str) -> None:
    await get_collection("drafts").delete_one({"user_id": user_id})


# ── Profiles ──────────────────────────────────────────────────────────────

async def create_profile(
    user_id: str,
    participant_type: str,
    fields: dict,
    status: str = "active",
    ai_profile: str | None = None,
    ai_profile_draft: str | None = None,
    ai_profile_status: str = "none",
    ai_profile_updated_at: datetime | None = None,
    completeness: int = 0,
) -> dict:
    now = datetime.now(timezone.utc)
    doc = {
        "user_id": user_id,
        "participant_type": participant_type,
        "status": status,
        "fields": fields,
        "ai_profile": ai_profile,
        "ai_profile_draft": ai_profile_draft,
        "ai_profile_status": ai_profile_status,
        "ai_profile_updated_at": ai_profile_updated_at,
        "completeness": completeness,
        "created_at": now,
        "updated_at": now,
    }
    result = await get_collection("profiles").insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def get_profile_by_user(user_id: str) -> dict | None:
    return await get_collection("profiles").find_one({"user_id": user_id})


async def get_profile_by_id(profile_id: str) -> dict | None:
    return await get_collection("profiles").find_one({"_id": profile_id})


async def update_profile(profile_id: str, updates: dict) -> dict | None:
    updates["updated_at"] = datetime.now(timezone.utc)
    return await get_collection("profiles").find_one_and_update(
        {"_id": profile_id},
        {"$set": updates},
        return_document=True,
    )


async def list_profiles(
    participant_type: str,
    status: str = "active",
    skip: int = 0,
    limit: int = 50,
) -> list[dict]:
    cursor = get_collection("profiles").find(
        {"participant_type": participant_type, "status": status}
    ).skip(skip).limit(limit)
    return await cursor.to_list(length=limit)


# ── Applications ──────────────────────────────────────────────────────────

async def create_application(
    participant_type: str,
    submitted_fields: dict,
    submitted_completeness: int,
    *,
    user_id: str | None = None,
    draft_id: str | None = None,
    applicant_email: str | None = None,
) -> dict:
    """Create a pending application.

    - **Logged-in flow:** pass ``user_id`` and ``draft_id`` (submitted from a draft).
    - **Public apply flow:** pass ``applicant_email`` only; no user account exists yet.
    """
    now = datetime.now(timezone.utc)
    doc: dict[str, Any] = {
        "participant_type": participant_type,
        "submitted_fields": submitted_fields,
        "submitted_completeness": submitted_completeness,
        "submitted_at": now,
        "status": "pending",
        "admin_feedback": None,
        "created_at": now,
    }
    if user_id is not None:
        doc["user_id"] = user_id
    if draft_id is not None:
        doc["draft_id"] = str(draft_id)
    if applicant_email is not None:
        doc["applicant_email"] = applicant_email.strip().lower()

    if user_id is not None and draft_id is None:
        raise ValueError("draft_id is required when user_id is set")
    if user_id is None and not applicant_email:
        raise ValueError("applicant_email is required when user_id is not set")

    result = await get_collection("applications").insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def get_application(app_id: str) -> dict | None:
    return await get_collection("applications").find_one({"_id": app_id})


async def get_application_by_user(user_id: str) -> dict | None:
    return await get_collection("applications").find_one(
        {"user_id": user_id},
        sort=[("created_at", -1)],
    )


async def get_pending_application_by_user(user_id: str) -> dict | None:
    return await get_collection("applications").find_one(
        {"user_id": user_id, "status": "pending"},
        sort=[("created_at", -1)],
    )


async def get_pending_application_by_email(email: str) -> dict | None:
    """Pending application for this applicant email (public apply flow)."""
    normalized = email.strip().lower()
    return await get_collection("applications").find_one(
        {"status": "pending", "applicant_email": normalized},
    )


async def update_application(app_id: str, updates: dict) -> dict | None:
    return await get_collection("applications").find_one_and_update(
        {"_id": app_id},
        {"$set": updates},
        return_document=True,
    )


async def delete_application(app_id: str) -> None:
    await get_collection("applications").delete_one({"_id": app_id})


async def list_applications(
    status: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[dict]:
    query: dict[str, Any] = {}
    if status:
        query["status"] = status
    cursor = get_collection("applications").find(query).skip(skip).limit(limit)
    return await cursor.to_list(length=limit)
