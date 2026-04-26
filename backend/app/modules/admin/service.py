from __future__ import annotations

from typing import Any

from app.core.exceptions import NotFoundError
from app.core.marketplace_config import MarketplaceConfig
from app.modules.admin import repository as repo
from app.modules.ai import service as ai_service
from app.modules.files import repository as files_repo
from app.modules.files import service as files_service
from app.modules.profiles import repository as profiles_repo
from app.modules.profiles import service as profiles_service


# ── Dashboard ────────────────────────────────────────────────────────────

async def get_dashboard(config: MarketplaceConfig) -> dict[str, Any]:
    stats = await repo.get_dashboard_stats()
    stats["marketplace"] = {
        "name": config.marketplace.name,
        "industry": config.marketplace.industry,
        "participant_types": config.type_slugs(),
    }
    return stats


# ── User Listing ─────────────────────────────────────────────────────────

async def list_users(skip: int = 0, limit: int = 50) -> list[dict]:
    users = await repo.list_users(skip, limit)
    return [_serialize(u) for u in users]


# ── Applications ─────────────────────────────────────────────────────────

async def list_applications(status: str | None = None) -> list[dict]:
    apps = await profiles_repo.list_applications(status)
    return [_serialize(a) for a in apps]


async def approve_application(app_id: str) -> dict[str, Any]:
    return await profiles_service.approve_application(app_id)


async def reject_application(
    app_id: str, feedback: str | None = None
) -> dict[str, Any]:
    return await profiles_service.reject_application(app_id, feedback or "")


async def list_application_files(app_id: str) -> list[dict]:
    """List uploaded files attached to a pending or approved application.

    For pending applications the link is ``application_id``; once an admin
    approves, files are reassigned to the new ``profile_id``. We surface
    both so the admin sees the same file regardless of where it sits in
    the lifecycle.
    """
    by_app = await files_repo.list_files_for_application(app_id)
    application = await profiles_repo.get_application(app_id)
    by_profile: list[dict] = []
    if application and application.get("status") == "approved":
        # ``approve_application`` stores the resulting profile id on the
        # application as ``user_id`` (the resulting account); the matching
        # profile id is what the file points to. Look it up by user.
        user_id = application.get("user_id")
        if user_id:
            cursor = files_repo.get_collection("files").find({"user_id": user_id})
            by_profile = await cursor.to_list(length=200)

    seen_ids: set[str] = set()
    merged: list[dict] = []
    for doc in (*by_app, *by_profile):
        fid = str(doc.get("_id"))
        if fid in seen_ids:
            continue
        seen_ids.add(fid)
        # Resolve a downloadable URL even for private files (presigned).
        try:
            url = await files_service._resolve_file_url(  # noqa: SLF001
                doc, doc.get("privacy", "public")
            )
        except Exception:
            url = doc.get("url")
        merged.append({
            "id": fid,
            "filename": doc.get("filename"),
            "size_bytes": doc.get("size_bytes"),
            "content_type": doc.get("content_type"),
            "category": doc.get("category"),
            "privacy": doc.get("privacy"),
            "created_at": doc.get("created_at"),
            "url": url,
        })
    return merged


# ── Config Summary ───────────────────────────────────────────────────────

async def get_config_summary(config: MarketplaceConfig) -> dict[str, Any]:
    return {
        "marketplace": config.marketplace.model_dump(),
        "participant_types": [pt.model_dump() for pt in config.participant_types],
        "communication_rules": [r.model_dump() for r in config.communication.conversation_rules],
        "discovery": config.discovery.model_dump(),
    }


# ── User Management ─────────────────────────────────────────────────────

async def get_user(user_id: str) -> dict:
    user = await repo.get_user(user_id)
    if not user:
        raise NotFoundError("User not found")
    return _serialize(user)


async def update_user_role(user_id: str, role: str) -> dict:
    user = await repo.update_user_role(user_id, role)
    if not user:
        raise NotFoundError("User not found")
    return _serialize(user)


async def deactivate_user(user_id: str) -> dict:
    user = await repo.deactivate_user(user_id)
    if not user:
        raise NotFoundError("User not found")
    return _serialize(user)


async def activate_user(user_id: str) -> dict:
    user = await repo.activate_user(user_id)
    if not user:
        raise NotFoundError("User not found")
    return _serialize(user)


# ── Profile Override ─────────────────────────────────────────────────────

async def get_profile_full(profile_id: str) -> dict:
    profile = await profiles_repo.get_profile_by_id(profile_id)
    if not profile:
        raise NotFoundError("Profile not found")
    return _serialize(profile)


async def update_profile_status(profile_id: str, status: str) -> dict:
    profile = await profiles_repo.update_profile(profile_id, {"status": status})
    if not profile:
        raise NotFoundError("Profile not found")
    return _serialize(profile)


# ── Conversation Oversight ───────────────────────────────────────────────

async def list_all_conversations(
    skip: int = 0, limit: int = 50, status: str | None = None
) -> list[dict]:
    convos = await repo.list_all_conversations(skip, limit, status)
    return [_serialize(c) for c in convos]


async def get_conversation_messages(
    conversation_id: str, skip: int = 0, limit: int = 50
) -> list[dict]:
    msgs = await repo.get_conversation_messages(conversation_id, skip, limit)
    return [_serialize(m) for m in msgs]


# ── AI / LLM (delegates to ai_service) ──────────────────────────────────

async def get_llm_settings() -> dict:
    return await ai_service.get_llm_settings()


async def update_llm_settings(updates: dict) -> dict:
    return await ai_service.update_llm_settings(updates)


async def get_models(provider: str | None = None) -> list[dict]:
    return await ai_service.get_models(provider)


async def get_providers() -> list[dict]:
    return await ai_service.get_providers()


async def validate_provider(provider_id: str) -> dict:
    return await ai_service.validate_provider(provider_id)


async def list_prompts() -> list[dict]:
    return await ai_service.list_prompts()


async def update_prompt(intent: str, template: str) -> dict:
    return await ai_service.update_prompt(intent, template)


async def list_documents(skip: int = 0, limit: int = 50) -> list[dict]:
    return await ai_service.list_documents(skip, limit)


async def delete_document(doc_id: str) -> None:
    return await ai_service.delete_document(doc_id)


# ── FAQ ──────────────────────────────────────────────────────────────────

async def create_faq(data: dict) -> dict:
    faq = await repo.create_faq(data)
    return _serialize(faq)


async def get_faq(faq_id: str) -> dict:
    faq = await repo.get_faq(faq_id)
    if not faq:
        raise NotFoundError("FAQ not found")
    return _serialize(faq)


async def update_faq(faq_id: str, updates: dict) -> dict:
    faq = await repo.update_faq(faq_id, updates)
    if not faq:
        raise NotFoundError("FAQ not found")
    return _serialize(faq)


async def delete_faq(faq_id: str) -> dict:
    found = await repo.get_faq(faq_id)
    if not found:
        raise NotFoundError("FAQ not found")
    await repo.delete_faq(faq_id)
    return {"deleted": True}


async def list_faqs(active_only: bool = False) -> list[dict]:
    faqs = await repo.list_faqs(active_only)
    return [_serialize(f) for f in faqs]


# ── Helpers ──────────────────────────────────────────────────────────────

def _serialize(doc: dict) -> dict:
    if doc is None:
        return {}
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc
