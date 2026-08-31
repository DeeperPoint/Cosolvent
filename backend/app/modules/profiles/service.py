from __future__ import annotations

import html
import secrets
from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from pydantic import ValidationError

from app.core.config import settings
from app.core.database import get_collection
from app.core.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.marketplace_config import MarketplaceConfig, get_marketplace_config
from app.core.security import hash_password

import logging
from app.core.queue import enqueue_job
from app.engine.schema_engine import compute_completeness, validate_profile_fields
from app.engine.visibility_engine import ViewerTier, filter_fields, get_viewer_tier
from app.modules.auth import repository as auth_repo
from app.modules.files import repository as files_repo
from app.modules.files import service as files_service
from app.modules.profiles.ai_generation import generate_profile_content
from app.modules.profiles import repository as repo
from app.modules.profiles.register_request import MAX_REGISTER_UPLOAD_FILES

logger = logging.getLogger("cosolvent")


async def register(user: dict, config: MarketplaceConfig, fields: dict | None = None) -> dict:
    """Create a draft for a newly registered user, optionally with fields."""
    user_id = str(user["_id"])
    pt = user.get("participant_type")

    existing = await repo.get_draft(user_id)
    if existing:
        raise ConflictError("Draft already exists")

    existing_profile = await repo.get_profile_by_user(user_id)
    if existing_profile:
        raise ConflictError("Profile already exists")

    validated = {}
    if fields:
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


async def submit_application_without_account(
    email: str,
    participant_type: str,
    config: MarketplaceConfig,
    fields: dict | None,
    file_parts: list[tuple[str, str, bytes]] | None = None,
) -> dict:
    """
    Public registration: store a pending application only (no user account, no session).
    Optional multipart file payloads ``file_parts`` as (filename, content_type, bytes).
    Admin approves via ``approve_application``, which creates the account and emails credentials.
    """
    if not email or not str(email).strip():
        raise AppError("email is required", status_code=422)

    normalized_email = str(email).strip().lower()

    if await auth_repo.find_user_by_email(normalized_email):
        raise ConflictError("Email already registered")

    if await repo.get_pending_application_by_email(normalized_email):
        raise ConflictError("A pending application already exists for this email")

    if not fields:
        raise AppError("Profile fields are required", status_code=422)

    uploads = file_parts or []
    if len(uploads) > MAX_REGISTER_UPLOAD_FILES:
        raise AppError(
            f"At most {MAX_REGISTER_UPLOAD_FILES} files may be attached to an application",
            status_code=422,
        )

    try:
        validated = validate_profile_fields(config, participant_type, fields)
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

    completeness = compute_completeness(config, participant_type, validated)

    onboarding = config.onboarding.get(participant_type)
    if not onboarding:
        raise AppError(f"No onboarding config for type '{participant_type}'")

    if completeness < onboarding.profile_completeness_threshold:
        raise AppError(
            f"Profile completeness {completeness}% below threshold "
            f"{onboarding.profile_completeness_threshold}%",
            status_code=422,
        )

    if onboarding.document_upload_required and len(uploads) < 1:
        raise AppError(
            "At least one onboarding document must be uploaded with this application",
            status_code=422,
        )

    app = await repo.create_application(
        participant_type=participant_type,
        submitted_fields=deepcopy(validated),
        submitted_completeness=completeness,
        applicant_email=normalized_email,
    )
    app_id = str(app["_id"])

    try:
        for filename, content_type, raw in uploads:
            if len(raw) > settings.files_max_upload_bytes:
                raise AppError("File exceeds upload size limit", status_code=413)
            await files_service.upload_file_for_application(
                app_id,
                config,
                BytesIO(raw),
                filename,
                content_type,
                len(raw),
                category="onboarding",
            )
    except Exception:
        await files_service.delete_stored_files_for_application(app_id)
        await repo.delete_application(app_id)
        raise

    return {"status": "pending_review", "application_id": app_id}


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
            participant_type=pt,
            submitted_fields=deepcopy(draft["fields"]),
            submitted_completeness=completeness,
            user_id=user_id,
            draft_id=draft_id,
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
        if user.get("email"):
            await _ensure_password_and_notify_approval(
                str(user["_id"]),
                user["email"],
                config.marketplace.name,
                onboarding.welcome_email_on_approval,
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


# ── Loop-1 clarify loop (GAP-12): ask one question, answer, watch the score jump ──
def _empty(value: Any) -> bool:
    return value in (None, "", []) or (isinstance(value, str) and not value.strip())


def _profile_strength(config: MarketplaceConfig, pt: str, fields: dict) -> int:
    """A 0-100 'profile strength' over ALL schema fields (required + optional). Distinct from
    onboarding `completeness` (required-only): strength keeps improving as optional detail is
    added, which is what the clarify loop drives — so answering a question always moves it."""
    schema = config.profile_schemas.get(pt)
    all_fields = list(schema.all_fields) if schema else []
    if not all_fields:
        return 100
    filled = sum(1 for f in all_fields if not _empty(fields.get(f.name)))
    return int((filled / len(all_fields)) * 100)


async def next_clarification(user: dict, config: MarketplaceConfig) -> dict:
    """Return the single most valuable clarifying question for the caller's profile: the first
    empty *required* field, else the first empty optional field. Same 'update-and-recompose'
    spine as a story `correct` — answering it fills the field and the profile-strength score jumps."""
    pt = str(user.get("participant_type", ""))
    user_id = str(user["_id"])
    raw_profile = await repo.get_profile_by_user(user_id)
    if raw_profile is not None:
        profile = _profile_response(raw_profile, config, "owner")
    else:
        draft = await repo.get_draft(user_id)
        if draft is None:
            raise NotFoundError("No profile or draft to clarify — register first")
        profile = _draft_response(draft)
    fields = (profile or {}).get("fields", {}) or {}
    schema = config.profile_schemas.get(pt)
    all_fields = list(schema.all_fields) if schema else []
    strength = _profile_strength(config, pt, fields)

    # A field extracted with low confidence is worth more than an empty optional one:
    # a wrong value already in the profile is misleading matching right now, whereas a
    # missing optional field merely leaves it thinner. Confirming beats collecting.
    intake = (profile or {}).get(INTAKE_KEY) or {}
    # Values extracted but held back because the model was unsure — confirming one
    # writes it to the canonical field, which is the whole point of asking.
    suggested = intake.get("suggested", {}) or {}
    uncertain = next((f for f in all_fields if f.name in suggested), None)

    candidate = (
        next((f for f in all_fields if f.required and _empty(fields.get(f.name))), None)
        or uncertain
        or next((f for f in all_fields if _empty(fields.get(f.name))), None)
    )
    if candidate is None:
        return {"question": None, "complete": True, "strength": strength}

    if candidate is uncertain:
        entry = suggested.get(candidate.name, {})
        current = entry.get("value")
        return {
            "field": candidate.name,
            "label": candidate.label,
            "type": candidate.type,
            "options": candidate.options,
            "required": candidate.required,
            "current_value": current,
            "confidence": entry.get("confidence"),
            "source": entry.get("source"),
            # Confirmation, not collection — the participant already told us this,
            # we are just unsure we read it correctly.
            "question": f"I read your {candidate.label.lower()} as \"{current}\" — is that right?",
            "strength": strength,
            "complete": False,
        }

    return {
        "field": candidate.name,
        "label": candidate.label,
        "type": candidate.type,
        "options": candidate.options,
        "required": candidate.required,
        "question": f"To strengthen your profile, what is your {candidate.label.lower()}?",
        "strength": strength,
        "complete": False,
    }


async def answer_clarification(user: dict, field: str, value: Any, config: MarketplaceConfig) -> dict:
    """Apply one clarifying answer and report the before/after profile strength (the visible jump)."""
    pt = str(user.get("participant_type", ""))
    profile = await get_my_profile(user, config)
    if not profile or not profile.get("id"):
        raise NotFoundError("No profile to clarify")
    fields = dict(profile.get("fields", {}) or {})
    before = _profile_strength(config, pt, fields)
    fields[field] = value
    updated = await update_profile(str(profile["id"]), user, fields, config)
    after = _profile_strength(config, pt, updated.get("fields", fields))
    return {
        "field": field,
        "value": value,
        "strength_before": before,
        "strength_after": after,
        "completeness": int(updated.get("completeness", 0)),
        "jumped": after - before,
    }


# Below this, an extracted value is treated as a suggestion to confirm rather than a
# fact to rely on — the clarify loop asks about it before the profile leans on it.
LOW_CONFIDENCE_THRESHOLD = 0.6

# Where the raw submission and per-field provenance live on the profile. Kept out of
# `fields` so it never collides with a marketplace-defined field name.
INTAKE_KEY = "_intake"


async def extract_from_prose(user: dict, text: str, config: MarketplaceConfig) -> dict:
    """GAP-11 whole-profile own-voice intake: read a paragraph of prose, extract canonical
    fields for the caller's schema, and apply the ones that validate.

    Both halves of the dual representation are kept: the canonical values go into
    ``fields`` (what gating and scoring read), and the raw submission plus each field's
    confidence and supporting excerpt go into ``_intake`` (what the clarify loop and
    nuance judgements read). Storing only the canonical half would discard the evidence;
    storing only a single prose blob would lose which text supported which value.
    """
    from app.modules.profiles.ai_extraction import extract_fields_from_document

    pt = str(user.get("participant_type", ""))

    # Extraction is a per-type onboarding capability, not a global one — the config
    # flag exists so an operator can decide, and a market may deliberately want the
    # demand side filling structured forms instead.
    onboarding = config.onboarding.get(pt)
    if onboarding is not None and not onboarding.ai_extraction_enabled:
        raise ForbiddenError(
            f"Prose extraction is not enabled for '{pt}'. "
            "Set onboarding.{pt}.ai_extraction_enabled to turn it on.".replace("{pt}", pt)
        )

    # Own-voice intake belongs at registration — the stories open with a participant
    # describing their position before any structured profile exists. A newly registered
    # user has a draft, not a profile, so extraction has to work against whichever exists
    # or the feature is unusable at exactly the moment it is meant to be used.
    user_id = str(user["_id"])
    raw_profile = await repo.get_profile_by_user(user_id)
    draft = None if raw_profile else await repo.get_draft(user_id)

    if raw_profile is not None:
        profile = _profile_response(raw_profile, config, "owner")
        target = "profile"
    elif draft is not None:
        profile = {"id": str(draft["_id"]), "fields": draft.get("fields", {}) or {}, **{INTAKE_KEY: draft.get(INTAKE_KEY)}}
        target = "draft"
    else:
        raise NotFoundError("No profile or draft to enrich — register first")

    schema = config.profile_schemas.get(pt)
    field_defs = [
        {"name": f.name, "type": f.type, "options": f.options}
        for f in (schema.all_fields if schema else [])
        if f.type not in ("file", "files")
    ]
    before = _profile_strength(config, pt, profile.get("fields", {}) or {})
    by_name = {f.name: f for f in (schema.all_fields if schema else [])}

    try:
        extracted = await extract_fields_from_document(text, pt, field_defs)
    except AppError:
        raise
    except Exception as exc:
        raise AppError(f"Could not extract from your description: {exc}", status_code=502) from exc

    base = dict(profile.get("fields", {}) or {})
    # Only seed `description` when the participant has not written one. Overwriting it
    # with the raw submission destroys text they authored; the raw text is preserved in
    # `_intake` either way.
    if _empty(base.get("description")) and "description" in by_name:
        base["description"] = text

    applied: list[str] = []
    rejected: list[dict[str, Any]] = []
    low_confidence: list[str] = []
    provenance: dict[str, Any] = {}
    # Values the model produced but was not confident about — kept out of `fields`
    # and offered to the clarify loop for confirmation.
    suggested: dict[str, Any] = {}

    for key, entry in (extracted or {}).items():
        fd = by_name.get(key)
        value = entry.get("value") if isinstance(entry, dict) else entry
        confidence = float(entry.get("confidence", 0.5)) if isinstance(entry, dict) else 0.5
        source = entry.get("source", "") if isinstance(entry, dict) else ""

        if fd is None:
            rejected.append({"field": key, "value": value, "reason": "not a field in this schema"})
            continue
        if _empty(value):
            continue

        coerced = _coerce_field_value(fd, value)
        if coerced is None:
            # Reported rather than dropped: silently skipping means a participant writes a
            # paragraph, the call succeeds, and the field just never appears.
            rejected.append(
                {"field": key, "value": value, "reason": f"not a valid {fd.type} value for this field"}
            )
            continue

        if confidence < LOW_CONFIDENCE_THRESHOLD:
            # Held back rather than written. A canonical field is what gating and
            # scoring read, so an inferred value there is worse than an absent one:
            # it silently distorts matching against a requirement the participant
            # never stated. Surfaced for the clarify loop to confirm instead.
            suggested[key] = {"value": coerced, "confidence": confidence, "source": source}
            low_confidence.append(key)
            continue

        base[key] = coerced
        applied.append(key)
        provenance[key] = {"confidence": confidence, "source": source}

    intake = {
        "raw_text": text,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "fields": provenance,
        "suggested": suggested,
    }

    completeness = compute_completeness(config, pt, base)
    if target == "profile":
        await repo.update_profile(
            str(profile["id"]),
            {"fields": base, "completeness": completeness, INTAKE_KEY: intake},
        )
        # Only a live profile belongs in the discovery index; a draft is not yet
        # discoverable, and indexing one would surface an unsubmitted participant.
        await _queue_profile_index(str(profile["id"]))
    else:
        await get_collection("drafts").update_one(
            {"_id": profile["id"]},
            {"$set": {"fields": base, "completeness": completeness, INTAKE_KEY: intake}},
        )

    after = _profile_strength(config, pt, base)
    return {
        "target": target,
        "applied": applied,
        "rejected": rejected,
        "suggested": suggested,
        "low_confidence": low_confidence,
        "extracted": extracted,
        "strength_before": before,
        "strength_after": after,
        "jumped": after - before,
        "completeness": completeness,
    }


async def extract_for_registration(
    participant_type: str, text: str, config: MarketplaceConfig
) -> dict:
    """Stateless own-voice intake for the *anonymous* registration form (GAP-11).

    Unlike ``extract_from_prose``, there is no account, draft or profile yet: this
    reads a paragraph of prose (typed, pasted, or dictated and transcribed in the
    browser) and returns the canonical field values the registration form should be
    pre-filled with. Nothing is persisted — the applicant reviews and edits the
    form, then submits it through the normal ``register`` path.

    Returned shape:
      - ``fields``    — ``{name: value}`` to merge into the form (includes low-confidence
                        guesses so the applicant can correct them in place)
      - ``filled``    — field names the model was confident about
      - ``uncertain`` — field names pre-filled from a low-confidence guess (highlight these)
      - ``rejected``  — ``[{field, value, reason}]`` the model produced that don't fit the schema
      - ``raw_text``  — the submission, echoed back
    """
    from app.modules.profiles.ai_extraction import extract_fields_from_document

    if config.get_type(participant_type) is None:
        raise NotFoundError(f"Unknown participant type: {participant_type}")

    # Extraction is a per-type onboarding capability — a market may deliberately
    # want one side filling the structured form by hand.
    onboarding = config.onboarding.get(participant_type)
    if onboarding is not None and not onboarding.ai_extraction_enabled:
        raise ForbiddenError(f"AI-assisted registration is not enabled for '{participant_type}'.")

    schema = config.profile_schemas.get(participant_type)
    by_name = {f.name: f for f in (schema.all_fields if schema else [])}
    field_defs = [
        {"name": f.name, "type": f.type, "options": f.options}
        for f in by_name.values()
        if f.type not in ("file", "files")
    ]
    if not field_defs:
        return {"fields": {}, "filled": [], "uncertain": [], "rejected": [], "raw_text": text}

    try:
        extracted = await extract_fields_from_document(text, participant_type, field_defs)
    except AppError:
        raise
    except Exception as exc:
        raise AppError(f"Could not read that description: {exc}", status_code=502) from exc

    fields: dict[str, Any] = {}
    filled: list[str] = []
    uncertain: list[str] = []
    rejected: list[dict[str, Any]] = []

    # The raw submission is the natural content of a free-text "About" field, if the
    # schema has one. The applicant can still edit or clear it before submitting.
    if "description" in by_name:
        fields["description"] = text

    for key, entry in (extracted or {}).items():
        fd = by_name.get(key)
        value = entry.get("value") if isinstance(entry, dict) else entry
        confidence = float(entry.get("confidence", 0.5)) if isinstance(entry, dict) else 0.5

        if fd is None:
            rejected.append({"field": key, "value": value, "reason": "not a field in this form"})
            continue
        if _empty(value):
            continue

        coerced = _coerce_field_value(fd, value)
        if coerced is None:
            rejected.append(
                {"field": key, "value": value, "reason": f"not a valid {fd.type} value"}
            )
            continue

        fields[key] = coerced
        # Both confident and unsure values pre-fill the form — the applicant reviews
        # everything anyway — but the unsure ones are flagged so the UI can highlight
        # them for a second look rather than burying them among the rest.
        if confidence < LOW_CONFIDENCE_THRESHOLD:
            uncertain.append(key)
        else:
            filled.append(key)

    logger.info(
        "Registration extraction for %s: %d filled, %d uncertain, %d rejected",
        participant_type, len(filled), len(uncertain), len(rejected),
    )
    return {
        "fields": fields,
        "filled": filled,
        "uncertain": uncertain,
        "rejected": rejected,
        "raw_text": text,
    }


def _coerce_field_value(field_def: Any, value: Any) -> Any:
    """Return a schema-valid value for one field, or None if it can't be made valid."""
    t = field_def.type
    opts = field_def.options or []
    if t == "select":
        return value if (not opts or value in opts) else None
    if t == "multi_select":
        vals = value if isinstance(value, list) else [value]
        kept = [v for v in vals if (not opts or v in opts)]
        return kept or None
    if t == "number":
        try:
            return float(value) if isinstance(value, str) and "." in value else int(value)
        except (TypeError, ValueError):
            return None
    if t in ("text", "rich_text", "date", "location"):
        s = str(value).strip()
        return s or None
    return None


async def approve_application(app_id: str, feedback: str = "") -> dict:
    application = await repo.get_application(app_id)
    if not application:
        raise NotFoundError("Application not found")
    if application["status"] != "pending":
        raise AppError("Application is not pending")

    submitted_fields = application.get("submitted_fields")
    submitted_completeness = application.get("submitted_completeness")

    # Public apply flow: no user account yet — admin approval creates user + profile + credentials email.
    if application.get("user_id") is None:
        email = application.get("applicant_email")
        if not email or not isinstance(submitted_fields, dict):
            raise AppError("Invalid pre-account application")

        if await auth_repo.find_user_by_email(email):
            raise ConflictError("Email already registered")

        approved_fields = deepcopy(submitted_fields)
        completeness = int(submitted_completeness) if isinstance(submitted_completeness, int) else 0

        plaintext = secrets.token_urlsafe(14)
        user = await auth_repo.create_user(
            email=email,
            password_hash=hash_password(plaintext),
            participant_type=application["participant_type"],
        )
        uid = str(user["_id"])
        profile = await repo.create_profile(
            user_id=uid,
            participant_type=application["participant_type"],
            fields=approved_fields,
            status="active",
            completeness=completeness,
        )
        await repo.update_application(
            app_id,
            {"status": "approved", "admin_feedback": feedback, "user_id": uid},
        )
        await get_collection("users").update_one(
            {"_id": uid},
            {"$set": {"has_onboarded": True}},
        )
        await _queue_profile_index(str(profile["_id"]))

        config = get_marketplace_config()
        await _queue_welcome_email_with_password(email, config.marketplace.name, plaintext)
        pid = str(profile["_id"])
        await files_repo.reassign_application_files_to_profile(app_id, uid, pid)
        return {"status": "approved", "profile_id": pid}

    # Logged-in flow: user and draft already existed at submission time.
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

    config = get_marketplace_config()
    user = await get_collection("users").find_one({"_id": application["user_id"]})
    if user and user.get("email"):
        pt = application.get("participant_type")
        onboarding = config.onboarding.get(pt) if pt else None
        welcome = onboarding.welcome_email_on_approval if onboarding else True
        await _ensure_password_and_notify_approval(
            application["user_id"],
            user["email"],
            config.marketplace.name,
            welcome,
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
        # Own-voice intake can run before submission, so the draft carries the same
        # provenance a profile does. A draft is only ever readable by its owner.
        INTAKE_KEY: draft.get(INTAKE_KEY),
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
        # Own-voice intake provenance (GAP-11) — the raw submission and per-field
        # confidence. Owner-only, like the AI profile above: the raw prose is what the
        # participant said before any visibility filtering, so exposing it to another
        # viewer would route around `filter_fields` entirely. The clarify loop reads it
        # through this projection, so omitting it silently disables confirmation questions.
        INTAKE_KEY: profile.get(INTAKE_KEY) if can_view_ai else None,
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
    body_html = (
        "<p>Your profile has been approved and is now active.</p>"
        "<p>You can start discovering participants and conversations immediately.</p>"
    )
    await enqueue_job(
        "app.workers.email_sender.send_email_task",
        to_email,
        subject,
        body_html,
        required=False,
    )


async def _queue_welcome_email_with_password(
    to_email: str, marketplace_name: str, plaintext_password: str
) -> None:
    subject = f"Welcome to {marketplace_name}"
    body_html = (
        "<p>Your profile has been approved and is now active.</p>"
        "<p>You can sign in with:</p>"
        "<ul>"
        f"<li>Email: {html.escape(to_email)}</li>"
        f"<li>Password: {html.escape(plaintext_password)}</li>"
        "</ul>"
        "<p>Please change your password after signing in.</p>"
    )
    await enqueue_job(
        "app.workers.email_sender.send_email_task",
        to_email,
        subject,
        body_html,
        required=False,
    )


async def _ensure_password_and_notify_approval(
    user_id: str,
    email: str | None,
    marketplace_name: str,
    welcome_email_on_approval: bool,
) -> None:
    """
    If the user was created without a password (email-only registration), generate one
    and email credentials. Otherwise send the standard welcome email when enabled.
    """
    if not email:
        return
    user = await get_collection("users").find_one({"_id": user_id})
    if not user:
        return
    if user.get("password_hash"):
        if welcome_email_on_approval:
            await _queue_welcome_email(email, marketplace_name)
        return
    plaintext = secrets.token_urlsafe(14)
    await get_collection("users").update_one(
        {"_id": user_id},
        {"$set": {"password_hash": hash_password(plaintext)}},
    )
    await _queue_welcome_email_with_password(email, marketplace_name, plaintext)
