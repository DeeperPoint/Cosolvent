"""Tests that four permission/onboarding flags declared in MarketplaceConfig but
previously unread by any service are now actually enforced:

- ``permissions.can_initiate_conversation`` / ``can_receive_conversation`` -- were
  compiled into generated artifacts but never checked; ``conversation_rules`` alone
  decided whether a conversation could start. Now both the pairwise rule AND the
  per-type flags must hold.
- ``onboarding.*.ai_profile_generation`` -- the sibling flag ``ai_extraction_enabled``
  already gated prose extraction; this one gated nothing, so AI profile generation
  ran regardless of the config.
- ``permissions.can_list`` -- declared on every test fixture, asserted by
  ``check_permission()`` unit tests, but no endpoint ever read it. ``discovery.list_type``
  is the query-less "browse" surface it gates (distinct from ``search()``, which is
  gated by the viewer's ``can_search``).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.marketplace_config import load_marketplace_config
from app.modules.communication import service as comm_service
from app.modules.discovery import service as discovery_service
from app.modules.profiles import service as profiles_service

FIXTURES = Path(__file__).parent.parent / "test_config"


def _agri():
    return load_marketplace_config(FIXTURES / "agriculture.yaml")


# ── can_initiate_conversation / can_receive_conversation ──────────────────

@pytest.fixture
def mock_comm_repo():
    with patch("app.modules.communication.service.repo") as mock:
        yield mock


@pytest.mark.asyncio
async def test_create_conversation_still_works_when_flags_allow(mock_comm_repo):
    # Baseline: buyer.can_initiate_conversation=True, producer.can_receive_conversation=True
    # in the fixture -- the new checks must not break the existing passing case.
    cfg = _agri()
    with patch("app.modules.auth.repository.find_user_by_id",
               new=AsyncMock(return_value={"_id": "u2", "participant_type": "producer", "has_onboarded": True})), \
         patch("app.modules.notifications.service.create_notification", new=AsyncMock()):
        mock_comm_repo.create_conversation = AsyncMock(return_value={"_id": "conv-1"})
        result = await comm_service.create_conversation(
            {"_id": "u1", "participant_type": "buyer", "has_onboarded": True}, "u2", None, cfg,
        )
    assert result["id"] == "conv-1"


@pytest.mark.asyncio
async def test_create_conversation_blocked_when_initiator_flag_off(mock_comm_repo):
    cfg = _agri()
    cfg.get_type("buyer").permissions.can_initiate_conversation = False
    with patch("app.modules.auth.repository.find_user_by_id",
               new=AsyncMock(return_value={"_id": "u2", "participant_type": "producer", "has_onboarded": True})):
        with pytest.raises(ForbiddenError, match="cannot initiate conversations"):
            await comm_service.create_conversation(
                {"_id": "u1", "participant_type": "buyer", "has_onboarded": True}, "u2", None, cfg,
            )
    mock_comm_repo.create_conversation.assert_not_called()


@pytest.mark.asyncio
async def test_create_conversation_blocked_when_receiver_flag_off(mock_comm_repo):
    cfg = _agri()
    cfg.get_type("producer").permissions.can_receive_conversation = False
    with patch("app.modules.auth.repository.find_user_by_id",
               new=AsyncMock(return_value={"_id": "u2", "participant_type": "producer", "has_onboarded": True})):
        with pytest.raises(ForbiddenError, match="cannot receive conversations"):
            await comm_service.create_conversation(
                {"_id": "u1", "participant_type": "buyer", "has_onboarded": True}, "u2", None, cfg,
            )
    mock_comm_repo.create_conversation.assert_not_called()


# ── ai_profile_generation ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ai_generate_profile_blocked_when_disabled():
    cfg = _agri()
    assert cfg.onboarding["buyer"].ai_profile_generation is False
    with patch("app.modules.profiles.service.repo") as mock_repo:
        mock_repo.get_profile_by_id = AsyncMock(
            return_value={"_id": "p1", "user_id": "u1", "participant_type": "buyer", "fields": {}}
        )
        with pytest.raises(ForbiddenError, match="AI profile generation is not enabled"):
            await profiles_service.ai_generate_profile("p1", {"_id": "u1", "role": "user"}, cfg)


@pytest.mark.asyncio
async def test_ai_generate_profile_allowed_when_enabled():
    cfg = _agri()
    assert cfg.onboarding["producer"].ai_profile_generation is True
    with patch("app.modules.profiles.service.repo") as mock_repo, \
         patch("app.modules.profiles.service.generate_profile_content", new=AsyncMock(return_value="summary")), \
         patch("app.modules.profiles.service.enqueue_job", new=AsyncMock()):
        mock_repo.get_profile_by_id = AsyncMock(
            return_value={"_id": "p1", "user_id": "u1", "participant_type": "producer", "fields": {}}
        )
        mock_repo.update_profile = AsyncMock(
            return_value={"_id": "p1", "ai_profile_draft": "summary", "ai_profile_status": "generated"}
        )
        result = await profiles_service.ai_generate_profile("p1", {"_id": "u1", "role": "user"}, cfg)
    assert result["status"] == "generated"


# ── can_list / discovery.list_type ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_type_rejects_type_without_can_list():
    cfg = _agri()
    assert cfg.get_type("buyer").permissions.can_list is False
    with pytest.raises(ForbiddenError, match="not listable"):
        await discovery_service.list_type(cfg, "buyer")


@pytest.mark.asyncio
async def test_list_type_rejects_unknown_type():
    cfg = _agri()
    with pytest.raises(NotFoundError):
        await discovery_service.list_type(cfg, "nonexistent")


@pytest.mark.asyncio
async def test_list_type_returns_filtered_public_fields_for_anonymous_viewer():
    cfg = _agri()
    assert cfg.get_type("producer").permissions.can_list is True
    with patch("app.modules.discovery.service.repo") as mock_repo:
        mock_repo.search_profiles = AsyncMock(return_value=[
            {"_id": "p1", "fields": {
                "farm_name": "Valley Farms", "country": "Canada",
                "primary_crops": ["Wheat"], "financial_notes": "secret",
            }},
        ])
        mock_repo.count_profiles = AsyncMock(return_value=1)
        out = await discovery_service.list_type(cfg, "producer", viewer=None, page=1, page_size=20)

    assert out["total"] == 1
    fields = out["results"][0]["fields"]
    assert fields["farm_name"] == "Valley Farms"
    # financial_notes is visibility: private -- must never reach an anonymous viewer.
    assert "financial_notes" not in fields
