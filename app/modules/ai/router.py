"""AI/RAG routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_config, get_current_user, require_admin
from app.core.marketplace_config import MarketplaceConfig
from app.modules.ai import service
from app.modules.ai.schemas import (
    DocumentUpload,
    FollowUpRequest,
    LLMSettingsUpdate,
    PromptUpdate,
    ProviderValidateRequest,
    QueryRequest,
)

router = APIRouter()


@router.post("/query")
async def query(
    body: QueryRequest,
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    return await service.query(user["_id"], body.query, body.thread_id, body.filters, config, use_case=body.use_case)


@router.post("/follow-up")
async def follow_up(
    body: FollowUpRequest,
    config: MarketplaceConfig = Depends(get_config),
    user: dict = Depends(get_current_user),
):
    return await service.follow_up(body.thread_id, config)


@router.post("/documents")
async def upload_document(
    body: DocumentUpload,
    user: dict = Depends(require_admin),
):
    return await service.upload_document(body.filename, body.content, body.content_type)


@router.get("/documents")
async def list_documents(
    skip: int = Query(0),
    limit: int = Query(50),
    user: dict = Depends(require_admin),
):
    return await service.list_documents(skip, limit)


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, user: dict = Depends(require_admin)):
    await service.delete_document(doc_id)
    return {"detail": "Deleted"}


@router.get("/models")
async def get_models(
    provider: str | None = Query(None),
    user: dict = Depends(require_admin),
):
    return await service.get_models(provider)


@router.get("/providers")
async def get_providers(user: dict = Depends(require_admin)):
    return await service.get_providers()


@router.post("/providers/validate")
async def validate_provider(
    body: ProviderValidateRequest,
    user: dict = Depends(require_admin),
):
    return await service.validate_provider(body.provider)


@router.get("/settings")
async def get_settings(user: dict = Depends(require_admin)):
    return await service.get_llm_settings()


@router.put("/settings")
async def update_settings(
    body: LLMSettingsUpdate,
    user: dict = Depends(require_admin),
):
    return await service.update_llm_settings(body.model_dump(exclude_none=True))


@router.get("/prompts")
async def list_prompts(user: dict = Depends(require_admin)):
    return await service.list_prompts()


@router.put("/prompts/{intent}")
async def update_prompt(
    intent: str,
    body: PromptUpdate,
    user: dict = Depends(require_admin),
):
    return await service.update_prompt(intent, body.template)
