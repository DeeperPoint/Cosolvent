from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from pydantic import ValidationError

from app.core.database import get_collection
from app.core.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.marketplace_config import MarketplaceConfig
from app.core.queue import enqueue_job
from app.engine.schema_engine import compute_completeness, validate_profile_fields
from app.engine.visibility_engine import ViewerTier, filter_fields, get_viewer_tier
from app.modules.files import repository as files_repo
from app.modules.profiles.ai_generation import generate_profile_content
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
    try:
        validated = validate_profile_fields(config, pt, fields)
    except ValidationError as exc:
        messages = []
        for err in exc.errors():
            loc = ".".join(str(part) for part in err.get("loc", []))
            msg = str(err.get("msg", "invalid field value"))
            messages.append(f"{loc}: {msg}" if loc else msg)
        raise AppError(
            "Profile draft fields are invalid: " + "; ".join(messages),
            status_code=422,
        ) from exc

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

    existing_profile = await repo.get_profile_by_user(user_id)
    if existing_profile:
        raise ConflictError("Profile already exists")

    pending_app = await repo.get_pending_application_by_user(user_id)
    if pending_app:
        return {"status": "pending_review", "application_id": str(pending_app["_id"])}

    # Check completeness threshold
    completeness = compute_completeness(config, pt, draft["fields"])
    if completeness < onboarding.profile_completeness_threshold:
        raise AppError(
            f"Profile completeness {completeness}% below threshold "
            f"{onboarding.profile_completeness_threshold}%"
        )

    draft_id = str(draft["_id"])
    if onboarding.document_upload_required:
        uploaded_count = await files_repo.count_files_for_profile_owner(user_id, draft_id)
        if uploaded_count < 1:
            raise AppError(
                "At least one onboarding document must be uploaded before submission",
                status_code=422,
            )

    if onboarding.requires_approval and onboarding.approval_type == "manual":
        # Create application for admin review
        app = await repo.create_application(
            user_id=user_id,
            participant_type=pt,
            draft_id=draft_id,
            submitted_fields=deepcopy(draft["fields"]),
            submitted_completeness=completeness,
        )
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
            {"_id": str(user["_id"])},
            {"$set": {"has_onboarded": True}},
        )
        await _queue_profile_index(str(profile["_id"]))
        if onboarding.welcome_email_on_approval and user.get("email"):
            await _queue_welcome_email(user["email"], config.marketplace.name)
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
    if tier != "owner" and profile.get("status") != "active":
        raise NotFoundError("Profile not found")
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
    try:
        validated = validate_profile_fields(config, pt, fields)
    except ValidationError as exc:
        messages = []
        for err in exc.errors():
            loc = ".".join(str(part) for part in err.get("loc", []))
            msg = str(err.get("msg", "invalid field value"))
            messages.append(f"{loc}: {msg}" if loc else msg)
        raise AppError(
            "Profile fields are invalid: " + "; ".join(messages),
            status_code=422,
        ) from exc
    completeness = compute_completeness(config, pt, validated)

    updated = await repo.update_profile(profile_id, {
        "fields": validated,
        "completeness": completeness,
    })
    await _queue_profile_index(profile_id)
    return _profile_response(updated, config, "owner")


async def approve_application(app_id: str, feedback: str = "") -> dict:
    application = await repo.get_application(app_id)
    if not application:
        raise NotFoundError("Application not found")
    if application["status"] != "pending":
        raise AppError("Application is not pending")

    submitted_fields = application.get("submitted_fields")
    submitted_completeness = application.get("submitted_completeness")
    if isinstance(submitted_fields, dict):
        approved_fields = deepcopy(submitted_fields)
        completeness = int(submitted_completeness) if isinstance(submitted_completeness, int) else 0
    else:
        draft = await repo.get_draft(application["user_id"])
        if not draft:
            raise AppError("Draft not found for this application")
        approved_fields = draft["fields"]
        completeness = 100

    profile = await repo.create_profile(
        user_id=application["user_id"],
        participant_type=application["participant_type"],
        fields=approved_fields,
        status="active",
        completeness=completeness,
    )
    await repo.delete_draft(application["user_id"])
    await repo.update_application(app_id, {"status": "approved", "admin_feedback": feedback})

    await get_collection("users").update_one(
        {"_id": application["user_id"]},
        {"$set": {"has_onboarded": True}},
    )
    await _queue_profile_index(str(profile["_id"]))

    user = await get_collection("users").find_one({"_id": application["user_id"]})
    if user and user.get("email"):
        await _queue_welcome_email(user["email"], "Cosolvent Marketplace")

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
    if profile["user_id"] != str(user["_id"]) and user.get("role") != "admin":
        raise ForbiddenError("Not your profile")

    summary = await generate_profile_content(
        fields=profile.get("fields", {}),
        participant_type=profile.get("participant_type", ""),
        marketplace_context=config.marketplace.description,
    )
    updated = await repo.update_profile(
        profile_id,
        {
            "ai_profile_draft": summary,
            "ai_profile_status": "generated",
            "ai_profile_updated_at": datetime.now(timezone.utc),
        },
    )
    return _ai_action_response(updated, "generated")


async def ai_approve_profile(profile_id: str) -> dict:
    profile = await repo.get_profile_by_id(profile_id)
    if not profile:
        raise NotFoundError("Profile not found")
    draft = profile.get("ai_profile_draft")
    if not draft:
        raise AppError("No generated AI profile draft to approve")

    updated = await repo.update_profile(
        profile_id,
        {
            "ai_profile": draft,
            "ai_profile_status": "approved",
            "ai_profile_updated_at": datetime.now(timezone.utc),
        },
    )
    return _ai_action_response(updated, "approved")


async def ai_reject_profile(profile_id: str) -> dict:
    profile = await repo.get_profile_by_id(profile_id)
    if not profile:
        raise NotFoundError("Profile not found")

    updated = await repo.update_profile(
        profile_id,
        {
            "ai_profile_draft": None,
            "ai_profile_status": "rejected",
            "ai_profile_updated_at": datetime.now(timezone.utc),
        },
    )
    return _ai_action_response(updated, "rejected")


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

    can_view_ai = tier == "owner"
    return {
        "id": str(profile["_id"]),
        "user_id": profile["user_id"],
        "participant_type": pt,
        "status": profile["status"],
        "fields": filtered,
        "ai_profile": profile.get("ai_profile") if can_view_ai else None,
        "ai_profile_draft": profile.get("ai_profile_draft") if can_view_ai else None,
        "ai_profile_status": profile.get("ai_profile_status", "none"),
        "ai_profile_updated_at": (
            str(profile.get("ai_profile_updated_at", "")) if profile.get("ai_profile_updated_at") else None
        ),
        "completeness": profile.get("completeness", 0),
        "created_at": str(profile.get("created_at", "")),
        "updated_at": str(profile.get("updated_at", "")),
    }


def _ai_action_response(profile: dict | None, action_status: str) -> dict:
    if not profile:
        raise AppError("Profile update failed")
    return {
        "status": action_status,
        "profile_id": str(profile["_id"]),
        "ai_profile": profile.get("ai_profile"),
        "ai_profile_draft": profile.get("ai_profile_draft"),
        "ai_profile_status": profile.get("ai_profile_status", "none"),
        "ai_profile_updated_at": (
            str(profile.get("ai_profile_updated_at", "")) if profile.get("ai_profile_updated_at") else None
        ),
    }


async def _queue_profile_index(profile_id: str) -> None:
    await enqueue_job(
        "app.workers.profile_indexing.index_profile_task",
        profile_id,
        required=False,
    )


async def _queue_welcome_email(to_email: str, marketplace_name: str) -> None:
    subject = f"Welcome to {marketplace_name}"
    html = (
        "<p>Your profile has been approved and is now active.</p>"
        "<p>You can start discovering participants and conversations immediately.</p>"
    )
    await enqueue_job(
        "app.workers.email_sender.send_email_task",
        to_email,
        subject,
        html,
        required=False,
    )
