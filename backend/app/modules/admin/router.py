"""Admin routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_config, require_admin
from app.core.marketplace_config import MarketplaceConfig
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
from app.modules.analytics.schemas import MarketOverview, MatchDensity
from app.modules.knowledge.schemas import EscapeHatchCreate

router = APIRouter()


# ── Knowledge gaps — Loop-2 pull signals (GAP-14) ────────────────────────
@router.get("/knowledge-gaps")
async def list_knowledge_gaps(
    status: str = Query("open"),
    user: dict = Depends(require_admin),
):
    from app.modules.knowledge import list_gap_signals

    return {"gaps": await list_gap_signals(status=status or None)}


@router.post("/knowledge-gaps/{gap_id}/resolve")
async def resolve_knowledge_gap(gap_id: str, user: dict = Depends(require_admin)):
    from app.modules.knowledge import set_gap_status

    ok = await set_gap_status(gap_id, "resolved")
    return {"resolved": ok}


# ── Escape hatches — Loop-2 conditional gates (GAP-14 payoff half) ────────
@router.get("/escape-hatches")
async def list_escape_hatches_route(
    status: str = Query("active"),
    user: dict = Depends(require_admin),
):
    from app.modules.knowledge import list_escape_hatches

    return {"hatches": await list_escape_hatches(status=status or None)}


@router.post("/escape-hatches")
async def create_escape_hatch_route(
    body: EscapeHatchCreate,
    user: dict = Depends(require_admin),
):
    from app.modules.knowledge import create_escape_hatch, set_gap_status

    hatch_id = await create_escape_hatch(
        gate_name=body.gate_name,
        condition=body.condition.model_dump(),
        rationale=body.rationale,
        vertical=body.vertical,
        metadata={"source_gap_id": body.source_gap_id} if body.source_gap_id else {},
    )
    # Ingesting a hatch answers the pull signal that motivated it.
    if body.source_gap_id:
        await set_gap_status(body.source_gap_id, "resolved")
    return {"id": hatch_id}


@router.post("/escape-hatches/{hatch_id}/deactivate")
async def deactivate_escape_hatch_route(hatch_id: str, user: dict = Depends(require_admin)):
    from app.modules.knowledge import set_escape_hatch_status

    ok = await set_escape_hatch_status(hatch_id, "inactive")
    return {"deactivated": ok}


# ── Dashboard & Config ───────────────────────────────────────────────────

@router.get("/dashboard")
async def dashboard(
    user: dict = Depends(require_admin),
    config: MarketplaceConfig = Depends(get_config),
):
    return await service.get_dashboard(config)


@router.get("/config")
async def get_config_summary(
    user: dict = Depends(require_admin),
    config: MarketplaceConfig = Depends(get_config),
):
    return await service.get_config_summary(config)


# ── Market-dynamics reporting (roadmap B1.8 'Market Physics Scorecard') ──
@router.get("/analytics/market-overview", response_model=MarketOverview)
async def market_overview(
    user: dict = Depends(require_admin),
    config: MarketplaceConfig = Depends(get_config),
):
    from app.modules.analytics import get_market_overview

    return await get_market_overview(config)


@router.get("/analytics/match-density", response_model=MatchDensity)
async def match_density(
    threshold: float = Query(0.75, ge=0.0, le=1.0, description="Minimum cosine similarity to count as a plausible pair"),
    sample_limit: int = Query(200, ge=1, le=500, description="Max active source-type profiles sampled per corridor"),
    user: dict = Depends(require_admin),
    config: MarketplaceConfig = Depends(get_config),
):
    """Approximate market thickness per supply->demand corridor. Heavier than
    market-overview (runs live pgvector queries) — see get_match_density's
    docstring for the approximation this makes."""
    from app.modules.analytics import get_match_density

    return await get_match_density(config, threshold=threshold, sample_limit=sample_limit)


# ── User Management ─────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    skip: int = Query(0),
    limit: int = Query(50),
    user: dict = Depends(require_admin),
):
    return await service.list_users(skip, limit)


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    user: dict = Depends(require_admin),
):
    return await service.get_user(user_id)


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    body: UserRoleUpdate,
    user: dict = Depends(require_admin),
):
    return await service.update_user_role(user_id, body.role)


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    user: dict = Depends(require_admin),
):
    return await service.deactivate_user(user_id)


@router.post("/users/{user_id}/activate")
async def activate_user(
    user_id: str,
    user: dict = Depends(require_admin),
):
    return await service.activate_user(user_id)


# ── Applications ─────────────────────────────────────────────────────────

@router.get("/applications")
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

@router.get("/profiles/{profile_id}")
async def get_profile(
    profile_id: str,
    user: dict = Depends(require_admin),
):
    return await service.get_profile_full(profile_id)


@router.put("/profiles/{profile_id}/status")
async def update_profile_status(
    profile_id: str,
    body: ProfileStatusUpdate,
    user: dict = Depends(require_admin),
):
    return await service.update_profile_status(profile_id, body.status)


# ── Conversation Oversight ───────────────────────────────────────────────

@router.get("/conversations")
async def list_conversations(
    skip: int = Query(0),
    limit: int = Query(50),
    status: str | None = Query(None),
    user: dict = Depends(require_admin),
):
    return await service.list_all_conversations(skip, limit, status)


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    skip: int = Query(0),
    limit: int = Query(50),
    user: dict = Depends(require_admin),
):
    return await service.get_conversation_messages(conversation_id, skip, limit)


# ── AI / LLM ────────────────────────────────────────────────────────────

@router.get("/ai/providers")
async def get_ai_providers(
    user: dict = Depends(require_admin),
):
    return await service.get_providers()


@router.post("/ai/providers/validate")
async def validate_ai_provider(
    body: ProviderValidateRequest,
    user: dict = Depends(require_admin),
):
    return await service.validate_provider(body.provider)


@router.get("/ai/models")
async def get_ai_models(
    provider: str | None = Query(None),
    user: dict = Depends(require_admin),
):
    return await service.get_models(provider)


@router.get("/ai/settings")
async def get_ai_settings(
    user: dict = Depends(require_admin),
):
    return await service.get_llm_settings()


@router.put("/ai/settings")
async def update_ai_settings(
    body: LLMSettingsUpdate,
    user: dict = Depends(require_admin),
):
    return await service.update_llm_settings(body.model_dump(exclude_none=True))


@router.get("/ai/prompts")
async def list_prompts(
    user: dict = Depends(require_admin),
):
    return await service.list_prompts()


@router.put("/ai/prompts/{intent}")
async def update_prompt(
    intent: str,
    body: PromptUpdate,
    user: dict = Depends(require_admin),
):
    return await service.update_prompt(intent, body.template)


@router.get("/ai/documents")
async def list_documents(
    skip: int = Query(0),
    limit: int = Query(50),
    user: dict = Depends(require_admin),
):
    return await service.list_documents(skip, limit)


@router.delete("/ai/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    user: dict = Depends(require_admin),
):
    await service.delete_document(doc_id)
    return {"deleted": True}


# ── FAQ ──────────────────────────────────────────────────────────────────

@router.get("/faqs")
async def list_faqs(
    active_only: bool = Query(False),
    user: dict = Depends(require_admin),
):
    return await service.list_faqs(active_only)


@router.post("/faqs")
async def create_faq(
    body: FAQCreate,
    user: dict = Depends(require_admin),
):
    return await service.create_faq(body.model_dump())


@router.get("/faqs/{faq_id}")
async def get_faq(
    faq_id: str,
    user: dict = Depends(require_admin),
):
    return await service.get_faq(faq_id)


@router.put("/faqs/{faq_id}")
async def update_faq(
    faq_id: str,
    body: FAQUpdate,
    user: dict = Depends(require_admin),
):
    return await service.update_faq(faq_id, body.model_dump(exclude_none=True))


@router.delete("/faqs/{faq_id}")
async def delete_faq(
    faq_id: str,
    user: dict = Depends(require_admin),
):
    return await service.delete_faq(faq_id)
