"""Tests for discovery service access, filtering, and retrieval semantics."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import AppError, ForbiddenError, NotFoundError, ServiceUnavailableError, UnauthorizedError
from app.core.marketplace_config import load_marketplace_config
from app.modules.discovery import service

FIXTURES = Path(__file__).parent.parent / "test_config"


def _config():
    return load_marketplace_config(FIXTURES / "agriculture.yaml")


@pytest.mark.asyncio
async def test_anonymous_search_disabled_by_default():
    cfg = _config()
    with pytest.raises(UnauthorizedError):
        await service.search(cfg, query="wheat", viewer=None)


@pytest.mark.asyncio
async def test_authenticated_user_without_can_search_is_forbidden():
    cfg = _config()
    viewer = {"_id": "u1", "participant_type": "producer", "role": "user", "has_onboarded": True}
    with pytest.raises(ForbiddenError):
        await service.search(cfg, query="wheat", viewer=viewer)


@pytest.mark.asyncio
async def test_unknown_filter_key_returns_422():
    cfg = _config()
    viewer = {"_id": "admin", "role": "admin"}
    with pytest.raises(AppError) as exc:
        await service.search(cfg, filters={"unknown": "x"}, viewer=viewer)
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_non_discoverable_type_returns_404():
    cfg = _config()
    viewer = {"_id": "admin", "role": "admin"}
    with pytest.raises(NotFoundError):
        await service.search(cfg, participant_type="buyer", viewer=viewer)


@pytest.mark.asyncio
async def test_anonymous_public_only_rejects_non_public_filters():
    cfg = _config()
    cfg.discovery.access.anonymous_search_enabled = True
    cfg.discovery.filter_fields.append("annual_production")
    viewer = None
    with pytest.raises(AppError) as exc:
        await service.search(
            cfg,
            participant_type="producer",
            filters={"annual_production": 42},
            viewer=viewer,
        )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_rag_strict_vector_failure_returns_503(monkeypatch):
    cfg = _config()
    cfg.discovery.ai.profile_retrieval_mode = "rag_strict"
    cfg.discovery.ai.rag_failure_behavior = "service_unavailable"
    viewer = {"_id": "admin", "role": "admin"}
    monkeypatch.setattr(service.settings, "openai_api_key", "test-key")

    with patch("app.modules.discovery.indexer._get_embedding", new=AsyncMock(side_effect=RuntimeError("boom"))):
        with pytest.raises(ServiceUnavailableError):
            await service.search(cfg, query="wheat", viewer=viewer)


@pytest.mark.asyncio
async def test_rag_strict_vector_failure_can_return_empty(monkeypatch):
    cfg = _config()
    cfg.discovery.ai.profile_retrieval_mode = "rag_strict"
    cfg.discovery.ai.rag_failure_behavior = "empty"
    viewer = {"_id": "admin", "role": "admin"}
    monkeypatch.setattr(service.settings, "openai_api_key", "test-key")

    with patch("app.modules.discovery.indexer._get_embedding", new=AsyncMock(side_effect=RuntimeError("boom"))):
        result = await service.search(cfg, query="wheat", viewer=viewer)
    assert result["results"] == []
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_hybrid_global_pagination_and_stable_order():
    cfg = _config()
    cfg.discovery.searchable_types = ["producer", "buyer"]
    for pt in cfg.participant_types:
        if pt.slug == "buyer":
            pt.permissions.visible_in_search = True
    viewer = {"_id": "admin", "role": "admin"}

    async def fake_search_profiles(participant_type, **_kwargs):
        if participant_type == "producer":
            return [
                {"_id": "b-id", "fields": {"farm_name": "B"}, "updated_at": "2024-01-01T00:00:00+00:00"},
            ]
        return [
            {"_id": "a-id", "fields": {"org_name": "A"}, "updated_at": "2025-01-01T00:00:00+00:00"},
        ]

    with patch.object(service.repo, "search_profiles", new=AsyncMock(side_effect=fake_search_profiles)), patch.object(
        service.repo,
        "count_profiles",
        new=AsyncMock(side_effect=[1, 1]),
    ):
        result = await service.search(cfg, viewer=viewer, page=1, page_size=1)

    assert result["total"] == 2
    assert len(result["results"]) == 1
    assert result["results"][0]["id"] == "a-id"


@pytest.mark.asyncio
async def test_ai_profile_is_hidden_for_non_owner_discovery_viewers():
    cfg = _config()
    viewer = {"_id": "buyer-user", "participant_type": "buyer", "role": "user", "has_onboarded": True}
    cfg.discovery.ai.vector_search_enabled = False

    docs = [
        {
            "_id": "p1",
            "fields": {"farm_name": "North Ridge", "country": "Canada"},
            "updated_at": "2025-01-01T00:00:00+00:00",
            "ai_profile": "secret summary",
        }
    ]
    with patch.object(service.repo, "search_profiles", new=AsyncMock(return_value=docs)), patch.object(
        service.repo,
        "count_profiles",
        new=AsyncMock(return_value=1),
    ):
        result = await service.search(cfg, query="ridge", participant_type="producer", viewer=viewer)
    assert result["results"][0]["ai_profile"] is None


@pytest.mark.asyncio
async def test_non_onboarded_user_with_required_onboarding_is_forbidden():
    cfg = _config()
    viewer = {"_id": "buyer-user", "participant_type": "buyer", "role": "user", "has_onboarded": False}
    with pytest.raises(ForbiddenError, match="Complete onboarding"):
        await service.search(cfg, query="wheat", participant_type="producer", viewer=viewer)
