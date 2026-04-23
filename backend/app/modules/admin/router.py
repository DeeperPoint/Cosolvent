"""Admin routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import get_config, require_admin
from app.core.marketplace_config import MarketplaceConfig
from app.core.response_models import DeletedResponse, JSONList, JSONObject
from app.modules.admin import service
from app.modules.admin.schemas import (
    ApplicationDecisionResponse,
    ApprovalAction,
    FAQCreate,
    FAQUpdate,
    ProfileStatusUpdate,
    UserRoleUpdate,
)
from app.modules.ai.schemas import LLMSettingsUpdate, PromptUpdate, ProviderValidateRequest

# Declare auth failure modes once at router scope so every admin operation
# surfaces 401 / 403 in the generated OpenAPI spec (they all pass through
# ``require_admin``).
_AUTH_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"description": "Not authenticated"},
    403: {"description": "Admin access required"},
}

router = APIRouter(responses=_AUTH_RESPONSES)


# ── Dashboard & Config ───────────────────────────────────────────────────

@router.get("/dashboard", response_model=JSONObject)
async def dashboard(
    user: dict = Depends(require_admin),
    config: MarketplaceConfig = Depends(get_config),
):
    return await service.get_dashboard(config)


@router.get("/config", response_model=JSONObject)
async def get_config_summary(
    user: dict = Depends(require_admin),
    config: MarketplaceConfig = Depends(get_config),
):
    return await service.get_config_summary(config)


# ── User Management ─────────────────────────────────────────────────────

@router.get("/users", response_model=JSONList)
async def list_users(
    skip: int = Query(0),
    limit: int = Query(50),
    user: dict = Depends(require_admin),
):
    return await service.list_users(skip, limit)


@router.get("/users/{user_id}", response_model=JSONObject)
async def get_user(
    user_id: str,
    user: dict = Depends(require_admin),
):
    return await service.get_user(user_id)


@router.put("/users/{user_id}/role", response_model=JSONObject)
async def update_user_role(
    user_id: str,
    body: UserRoleUpdate,
    user: dict = Depends(require_admin),
):
    return await service.update_user_role(user_id, body.role)


@router.post("/users/{user_id}/deactivate", response_model=JSONObject)
async def deactivate_user(
    user_id: str,
    user: dict = Depends(require_admin),
):
    return await service.deactivate_user(user_id)


@router.post("/users/{user_id}/activate", response_model=JSONObject)
async def activate_user(
    user_id: str,
    user: dict = Depends(require_admin),
):
    return await service.activate_user(user_id)


# ── Applications ─────────────────────────────────────────────────────────

@router.get("/applications", response_model=JSONList)
async def list_applications(
    status: str | None = Query(None),
    user: dict = Depends(require_admin),
):
    return await service.list_applications(status)


@router.post("/applications/{app_id}/approve", response_model=ApplicationDecisionResponse)
async def approve_application(
    app_id: str,
    user: dict = Depends(require_admin),
):
    return await service.approve_application(app_id)


@router.post("/applications/{app_id}/reject", response_model=ApplicationDecisionResponse)
async def reject_application(
    app_id: str,
    body: ApprovalAction = ApprovalAction(),
    user: dict = Depends(require_admin),
):
    return await service.reject_application(app_id, body.feedback)


# ── Profile Override ─────────────────────────────────────────────────────

@router.get("/profiles/{profile_id}", response_model=JSONObject)
async def get_profile(
    profile_id: str,
    user: dict = Depends(require_admin),
):
    return await service.get_profile_full(profile_id)


@router.put("/profiles/{profile_id}/status", response_model=JSONObject)
async def update_profile_status(
    profile_id: str,
    body: ProfileStatusUpdate,
    user: dict = Depends(require_admin),
):
    return await service.update_profile_status(profile_id, body.status)


# ── Conversation Oversight ───────────────────────────────────────────────

@router.get("/conversations", response_model=JSONList)
async def list_conversations(
    skip: int = Query(0),
    limit: int = Query(50),
    status: str | None = Query(None),
    user: dict = Depends(require_admin),
):
    return await service.list_all_conversations(skip, limit, status)


@router.get("/conversations/{conversation_id}/messages", response_model=JSONList)
async def get_conversation_messages(
    conversation_id: str,
    skip: int = Query(0),
    limit: int = Query(50),
    user: dict = Depends(require_admin),
):
    return await service.get_conversation_messages(conversation_id, skip, limit)


# ── AI / LLM ────────────────────────────────────────────────────────────

@router.get("/ai/providers", response_model=JSONList)
async def get_ai_providers(
    user: dict = Depends(require_admin),
):
    return await service.get_providers()


@router.post("/ai/providers/validate", response_model=JSONObject)
async def validate_ai_provider(
    body: ProviderValidateRequest,
    user: dict = Depends(require_admin),
):
    return await service.validate_provider(body.provider)


@router.get("/ai/models", response_model=JSONList)
async def get_ai_models(
    provider: str | None = Query(None),
    user: dict = Depends(require_admin),
):
    return await service.get_models(provider)


@router.get("/ai/settings", response_model=JSONObject)
async def get_ai_settings(
    user: dict = Depends(require_admin),
):
    return await service.get_llm_settings()


@router.put("/ai/settings", response_model=JSONObject)
async def update_ai_settings(
    body: LLMSettingsUpdate,
    user: dict = Depends(require_admin),
):
    return await service.update_llm_settings(body.model_dump(exclude_none=True))


@router.get("/ai/prompts", response_model=JSONList)
async def list_prompts(
    user: dict = Depends(require_admin),
):
    return await service.list_prompts()


@router.put("/ai/prompts/{intent}", response_model=JSONObject)
async def update_prompt(
    intent: str,
    body: PromptUpdate,
    user: dict = Depends(require_admin),
):
    return await service.update_prompt(intent, body.template)


@router.get("/ai/documents", response_model=JSONList)
async def list_documents(
    skip: int = Query(0),
    limit: int = Query(50),
    user: dict = Depends(require_admin),
):
    return await service.list_documents(skip, limit)


@router.delete("/ai/documents/{doc_id}", response_model=DeletedResponse)
async def delete_document(
    doc_id: str,
    user: dict = Depends(require_admin),
):
    await service.delete_document(doc_id)
    return {"deleted": True}


# ── FAQ ──────────────────────────────────────────────────────────────────

@router.get("/faqs", response_model=JSONList)
async def list_faqs(
    active_only: bool = Query(False),
    user: dict = Depends(require_admin),
):
    return await service.list_faqs(active_only)


@router.post(
    "/faqs",
    response_model=JSONObject,
    status_code=status.HTTP_201_CREATED,
    summary="Create FAQ",
)
async def create_faq(
    body: FAQCreate,
    user: dict = Depends(require_admin),
):
    return await service.create_faq(body.model_dump())


@router.get("/faqs/{faq_id}", response_model=JSONObject)
async def get_faq(
    faq_id: str,
    user: dict = Depends(require_admin),
):
    return await service.get_faq(faq_id)


@router.put("/faqs/{faq_id}", response_model=JSONObject)
async def update_faq(
    faq_id: str,
    body: FAQUpdate,
    user: dict = Depends(require_admin),
):
    return await service.update_faq(faq_id, body.model_dump(exclude_none=True))


@router.delete("/faqs/{faq_id}", response_model=JSONObject)
async def delete_faq(
    faq_id: str,
    user: dict = Depends(require_admin),
):
    return await service.delete_faq(faq_id)
