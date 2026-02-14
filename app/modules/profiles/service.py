from __future__ import annotations

from app.core.database import get_collection
from app.core.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.marketplace_config import MarketplaceConfig
from app.engine.schema_engine import compute_completeness, validate_profile_fields
from app.engine.visibility_engine import ViewerTier, filter_fields, get_viewer_tier
from app.modules.profiles import repository as repo


async def register(user: dict, config: MarketplaceConfig) -> dict:
    """Create an empty draft for a newly registered user."""
    user_id = str(user["_id"])
    pt = user.get("participant_type")

    existing = await repo.get_draft(user_id)
    if existing:
        raise ConflictError("Draft already exists")

    existing_profile = await repo.get_profile_by_user(user_id)
    if existing_profile:
        raise ConflictError("Profile already exists")

    draft = await repo.upsert_draft(user_id, pt, {})
    return _draft_response(draft)


async def get_draft(user: dict) -> dict:
    user_id = str(user["_id"])
    draft = await repo.get_draft(user_id)
    if not draft:
        raise NotFoundError("No draft found")
    return _draft_response(draft)


async def update_draft(user: dict, fields: dict, config: MarketplaceConfig) -> dict:
    user_id = str(user["_id"])
    pt = user.get("participant_type")

    # Validate fields against config schema
    validated = validate_profile_fields(config, pt, fields)

    draft = await repo.upsert_draft(user_id, pt, validated)
    return _draft_response(draft)


async def submit_draft(user: dict, config: MarketplaceConfig) -> dict:
    """Submit draft for approval (or auto-approve)."""
    user_id = str(user["_id"])
    pt = user.get("participant_type")
    draft = await repo.get_draft(user_id)
    if not draft:
        raise NotFoundError("No draft found")

    onboarding = config.onboarding.get(pt)
    if not onboarding:
        raise AppError(f"No onboarding config for type '{pt}'")

    # Check completeness threshold
    completeness = compute_completeness(config, pt, draft["fields"])
    if completeness < onboarding.profile_completeness_threshold:
        raise AppError(
            f"Profile completeness {completeness}% below threshold "
            f"{onboarding.profile_completeness_threshold}%"
        )

    if onboarding.requires_approval and onboarding.approval_type == "manual":
        # Create application for admin review
        app = await repo.create_application(user_id, pt, str(draft["_id"]))
        return {"status": "pending_review", "application_id": str(app["_id"])}
    else:
        # Auto-approve: create profile directly
        profile = await repo.create_profile(
            user_id=user_id,
            participant_type=pt,
            fields=draft["fields"],
            status="active",
            completeness=completeness,
        )
        await repo.delete_draft(user_id)
        await get_collection("users").update_one(
            {"_id": user["_id"] if not isinstance(user["_id"], str) else user["_id"]},
            {"$set": {"has_onboarded": True}},
        )
        return {"status": "active", "profile_id": str(profile["_id"])}


async def get_my_profile(user: dict, config: MarketplaceConfig) -> dict:
    user_id = str(user["_id"])
    profile = await repo.get_profile_by_user(user_id)
    if not profile:
        raise NotFoundError("No profile found")
    return _profile_response(profile, config, "owner")


async def get_profile(
    profile_id: str,
    type_slug: str,
    config: MarketplaceConfig,
    current_user: dict | None = None,
) -> dict:
    profile = await repo.get_profile_by_id(profile_id)
    if not profile or profile["participant_type"] != type_slug:
        raise NotFoundError("Profile not found")

    is_owner = current_user and str(current_user["_id"]) == profile["user_id"]
    is_admin = current_user and current_user.get("role") == "admin"
    tier = get_viewer_tier(
        is_authenticated=current_user is not None,
        is_owner=is_owner,
        is_admin=is_admin,
    )
    return _profile_response(profile, config, tier)


async def update_profile(
    profile_id: str,
    user: dict,
    fields: dict,
    config: MarketplaceConfig,
) -> dict:
    profile = await repo.get_profile_by_id(profile_id)
    if not profile:
        raise NotFoundError("Profile not found")
    if profile["user_id"] != str(user["_id"]) and user.get("role") != "admin":
        raise ForbiddenError("Not your profile")

    pt = profile["participant_type"]
    validated = validate_profile_fields(config, pt, fields)
    completeness = compute_completeness(config, pt, validated)

    updated = await repo.update_profile(profile_id, {
        "fields": validated,
        "completeness": completeness,
    })
    return _profile_response(updated, config, "owner")


async def approve_application(app_id: str, feedback: str = "") -> dict:
    application = await repo.get_application(app_id)
    if not application:
        raise NotFoundError("Application not found")
    if application["status"] != "pending":
        raise AppError("Application is not pending")

    draft = await repo.get_draft(application["user_id"])
    if not draft:
        raise AppError("Draft not found for this application")

    profile = await repo.create_profile(
        user_id=application["user_id"],
        participant_type=application["participant_type"],
        fields=draft["fields"],
        status="active",
        completeness=100,
    )
    await repo.delete_draft(application["user_id"])
    await repo.update_application(app_id, {"status": "approved", "admin_feedback": feedback})

    from bson import ObjectId
    await get_collection("users").update_one(
        {"_id": ObjectId(application["user_id"])},
        {"$set": {"has_onboarded": True}},
    )

    return {"status": "approved", "profile_id": str(profile["_id"])}


async def reject_application(app_id: str, feedback: str = "") -> dict:
    application = await repo.get_application(app_id)
    if not application:
        raise NotFoundError("Application not found")
    if application["status"] != "pending":
        raise AppError("Application is not pending")

    await repo.update_application(app_id, {"status": "rejected", "admin_feedback": feedback})
    return {"status": "rejected", "feedback": feedback}


# ── AI profile features (stubs for Phase 5) ──────────────────────────────

async def ai_generate_profile(profile_id: str, user: dict, config: MarketplaceConfig) -> dict:
    profile = await repo.get_profile_by_id(profile_id)
    if not profile:
        raise NotFoundError("Profile not found")
    # Stub — will be implemented in Phase 5
    return {"status": "ai_generation_not_implemented"}


async def ai_approve_profile(profile_id: str) -> dict:
    return {"status": "not_implemented"}


async def ai_reject_profile(profile_id: str) -> dict:
    return {"status": "not_implemented"}


# ── Response helpers ──────────────────────────────────────────────────────

def _draft_response(draft: dict) -> dict:
    return {
        "id": str(draft["_id"]),
        "user_id": draft["user_id"],
        "participant_type": draft["participant_type"],
        "status": draft["status"],
        "fields": draft["fields"],
        "created_at": str(draft.get("created_at", "")),
        "updated_at": str(draft.get("updated_at", "")),
    }


def _profile_response(profile: dict, config: MarketplaceConfig, tier: ViewerTier) -> dict:
    pt = profile["participant_type"]
    schema = config.profile_schemas.get(pt)
    filtered = filter_fields(schema, profile["fields"], tier) if schema else profile["fields"]

    return {
        "id": str(profile["_id"]),
        "user_id": profile["user_id"],
        "participant_type": pt,
        "status": profile["status"],
        "fields": filtered,
        "ai_profile": profile.get("ai_profile"),
        "completeness": profile.get("completeness", 0),
        "created_at": str(profile.get("created_at", "")),
        "updated_at": str(profile.get("updated_at", "")),
    }
