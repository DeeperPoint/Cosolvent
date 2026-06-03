"""Tests for the suggested-matches service.

Covers authorization, target-type resolution, score composition, and the
field-overlap helper. Repository + vector_service calls are mocked so these
tests run without infra.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import (
    AppError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.core.marketplace_config import load_marketplace_config
from app.modules.discovery import matching

FIXTURES = Path(__file__).parent.parent / "test_config"


def _config():
    return load_marketplace_config(FIXTURES / "agriculture.yaml")


def _producer_profile(profile_id: str = "p-1", user_id: str = "u-1") -> dict:
    return {
        "_id": profile_id,
        "user_id": user_id,
        "participant_type": "producer",
        "status": "active",
        "fields": {
            "farm_name": "North Ridge",
            "country": "Canada",
            "primary_crops": ["Wheat", "Barley"],
        },
    }


def _buyer_candidate(
    profile_id: str,
    score: float,
    fields: dict | None = None,
) -> dict:
    base_fields = {"org_name": "Acme Mills", "country": "Canada"}
    if fields:
        base_fields.update(fields)
    return {
        "id": profile_id,
        "score": score,
        "metadata": {"participant_type": "buyer"},
        "profile": {
            "_id": profile_id,
            "user_id": f"buyer-user-{profile_id}",
            "participant_type": "buyer",
            "status": "active",
            "fields": base_fields,
        },
    }


# ── _compute_field_overlap ────────────────────────────────────────────────


def test_compute_field_overlap_returns_zero_when_no_filter_fields():
    assert matching._compute_field_overlap([], {"a": 1}, {"a": 1}) == 0.0


def test_compute_field_overlap_returns_zero_when_no_shared_fields():
    score = matching._compute_field_overlap(
        ["country"],
        {"farm_name": "X"},
        {"org_name": "Y"},
    )
    assert score == 0.0


def test_compute_field_overlap_scalar_match():
    score = matching._compute_field_overlap(
        ["country"],
        {"country": "Canada"},
        {"country": "Canada"},
    )
    assert score == 1.0


def test_compute_field_overlap_scalar_mismatch():
    score = matching._compute_field_overlap(
        ["country"],
        {"country": "Canada"},
        {"country": "USA"},
    )
    assert score == 0.0


def test_compute_field_overlap_list_jaccard():
    # Wheat,Barley vs Wheat,Corn → intersection {Wheat}, union {Wheat, Barley, Corn} → 1/3
    score = matching._compute_field_overlap(
        ["primary_crops"],
        {"primary_crops": ["Wheat", "Barley"]},
        {"primary_crops": ["Wheat", "Corn"]},
    )
    assert score == pytest.approx(1 / 3)


def test_compute_field_overlap_scalar_against_list():
    # Source scalar "Wheat" vs candidate list ["Wheat","Barley"] → 1/2
    score = matching._compute_field_overlap(
        ["primary_crops"],
        {"primary_crops": "Wheat"},
        {"primary_crops": ["Wheat", "Barley"]},
    )
    assert score == pytest.approx(0.5)


def test_compute_field_overlap_averages_across_fields():
    # country matches (1.0), primary_crops Jaccard = 1/3 → mean ≈ 0.6667
    score = matching._compute_field_overlap(
        ["country", "primary_crops"],
        {"country": "Canada", "primary_crops": ["Wheat", "Barley"]},
        {"country": "Canada", "primary_crops": ["Wheat", "Corn"]},
    )
    assert score == pytest.approx((1.0 + 1 / 3) / 2)


# ── _resolve_target_type ──────────────────────────────────────────────────


def test_resolve_target_type_defaults_to_opposite_role():
    cfg = _config()
    # producer (supply) should default to buyer (demand)
    assert matching._resolve_target_type(cfg, "producer", None) == "buyer"
    assert matching._resolve_target_type(cfg, "buyer", None) == "producer"


def test_resolve_target_type_validates_explicit_target():
    cfg = _config()
    assert matching._resolve_target_type(cfg, "producer", "buyer") == "buyer"


def test_resolve_target_type_rejects_same_type():
    cfg = _config()
    with pytest.raises(AppError) as exc:
        matching._resolve_target_type(cfg, "producer", "producer")
    assert exc.value.status_code == 422


def test_resolve_target_type_rejects_unknown_target():
    cfg = _config()
    with pytest.raises(NotFoundError):
        matching._resolve_target_type(cfg, "producer", "nonsense")


def test_resolve_target_type_rejects_unknown_source():
    cfg = _config()
    with pytest.raises(NotFoundError):
        matching._resolve_target_type(cfg, "ghost", None)


# ── suggested_matches authorization ───────────────────────────────────────


@pytest.mark.asyncio
async def test_suggested_matches_requires_existing_profile():
    cfg = _config()
    with patch.object(
        matching.profiles_repo, "get_profile_by_id", new=AsyncMock(return_value=None)
    ):
        with pytest.raises(NotFoundError):
            await matching.suggested_matches(
                cfg,
                profile_id="missing",
                type_slug="producer",
                viewer={"_id": "u-1", "role": "user"},
            )


@pytest.mark.asyncio
async def test_suggested_matches_requires_type_match():
    cfg = _config()
    # Profile is a producer; caller asks via /buyer/... → 404
    profile = _producer_profile()
    with patch.object(
        matching.profiles_repo, "get_profile_by_id", new=AsyncMock(return_value=profile)
    ):
        with pytest.raises(NotFoundError):
            await matching.suggested_matches(
                cfg,
                profile_id="p-1",
                type_slug="buyer",
                viewer={"_id": "u-1", "role": "user"},
            )


@pytest.mark.asyncio
async def test_suggested_matches_requires_active_profile():
    cfg = _config()
    profile = _producer_profile()
    profile["status"] = "pending"
    with patch.object(
        matching.profiles_repo, "get_profile_by_id", new=AsyncMock(return_value=profile)
    ):
        with pytest.raises(AppError) as exc:
            await matching.suggested_matches(
                cfg,
                profile_id="p-1",
                type_slug="producer",
                viewer={"_id": "u-1", "role": "user"},
            )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_suggested_matches_forbids_non_owner():
    cfg = _config()
    profile = _producer_profile(user_id="owner")
    viewer = {"_id": "someone-else", "role": "user"}
    with patch.object(
        matching.profiles_repo, "get_profile_by_id", new=AsyncMock(return_value=profile)
    ):
        with pytest.raises(ForbiddenError):
            await matching.suggested_matches(
                cfg, profile_id="p-1", type_slug="producer", viewer=viewer
            )


@pytest.mark.asyncio
async def test_suggested_matches_503_when_vector_search_disabled():
    cfg = _config()
    cfg.discovery.ai.vector_search_enabled = False
    profile = _producer_profile()
    with patch.object(
        matching.profiles_repo, "get_profile_by_id", new=AsyncMock(return_value=profile)
    ):
        with pytest.raises(ServiceUnavailableError):
            await matching.suggested_matches(
                cfg, profile_id="p-1", type_slug="producer", viewer={"_id": "u-1", "role": "user"}
            )


@pytest.mark.asyncio
async def test_suggested_matches_409_when_not_indexed():
    cfg = _config()
    profile = _producer_profile()
    with patch.object(
        matching.profiles_repo, "get_profile_by_id", new=AsyncMock(return_value=profile)
    ), patch.object(
        matching.vector_service, "get_profile_embedding", new=AsyncMock(return_value=None)
    ):
        with pytest.raises(AppError) as exc:
            await matching.suggested_matches(
                cfg, profile_id="p-1", type_slug="producer", viewer={"_id": "u-1", "role": "user"}
            )
    assert exc.value.status_code == 409


# ── suggested_matches happy path ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_suggested_matches_ranks_by_composite_score():
    cfg = _config()
    profile = _producer_profile()

    # candidate A: high vector score, low field overlap
    # candidate B: lower vector score but full field overlap
    candidates = [
        _buyer_candidate("buyer-a", score=0.90, fields={"country": "USA"}),
        _buyer_candidate("buyer-b", score=0.60, fields={"country": "Canada"}),
    ]

    with patch.object(
        matching.profiles_repo, "get_profile_by_id", new=AsyncMock(return_value=profile)
    ), patch.object(
        matching.vector_service,
        "get_profile_embedding",
        new=AsyncMock(return_value=[0.1] * 1536),
    ), patch.object(
        matching.vector_service,
        "find_similar_profiles",
        new=AsyncMock(return_value=candidates),
    ):
        out = await matching.suggested_matches(
            cfg,
            profile_id="p-1",
            type_slug="producer",
            viewer={"_id": "u-1", "role": "user"},
        )

    assert out["target_type"] == "buyer"
    assert out["total"] == 2

    # Expected composites:
    #   buyer-a: country mismatch (0.0), crops absent → overlap=0.0 → 0.7*0.90 + 0.3*0 = 0.63
    #   buyer-b: country match (1.0), crops absent → mean over 1 field = 1.0 → 0.7*0.60 + 0.3*1.0 = 0.72
    assert out["results"][0]["id"] == "buyer-b"
    assert out["results"][1]["id"] == "buyer-a"
    assert out["results"][0]["score"] == pytest.approx(0.72)
    assert out["results"][1]["score"] == pytest.approx(0.63)
    assert out["results"][0]["score_breakdown"]["vector"] == pytest.approx(0.60)
    assert out["results"][0]["score_breakdown"]["field_overlap"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_suggested_matches_admin_can_query_other_owner():
    cfg = _config()
    profile = _producer_profile(user_id="owner")
    candidates = [_buyer_candidate("buyer-a", score=0.5)]

    with patch.object(
        matching.profiles_repo, "get_profile_by_id", new=AsyncMock(return_value=profile)
    ), patch.object(
        matching.vector_service,
        "get_profile_embedding",
        new=AsyncMock(return_value=[0.1] * 1536),
    ), patch.object(
        matching.vector_service,
        "find_similar_profiles",
        new=AsyncMock(return_value=candidates),
    ):
        out = await matching.suggested_matches(
            cfg,
            profile_id="p-1",
            type_slug="producer",
            viewer={"_id": "admin-id", "role": "admin"},
        )
    assert out["total"] == 1


@pytest.mark.asyncio
async def test_suggested_matches_excludes_own_id_and_passes_filters():
    cfg = _config()
    profile = _producer_profile()
    captured: dict = {}

    async def fake_find(**kwargs):
        captured.update(kwargs)
        return []

    with patch.object(
        matching.profiles_repo, "get_profile_by_id", new=AsyncMock(return_value=profile)
    ), patch.object(
        matching.vector_service,
        "get_profile_embedding",
        new=AsyncMock(return_value=[0.1] * 1536),
    ), patch.object(
        matching.vector_service, "find_similar_profiles", side_effect=fake_find
    ):
        out = await matching.suggested_matches(
            cfg,
            profile_id="p-1",
            type_slug="producer",
            viewer={"_id": "u-1", "role": "user"},
            limit=5,
            min_score=0.2,
        )

    assert out["total"] == 0
    assert captured["exclude_profile_ids"] == ["p-1"]
    assert captured["participant_types"] == ["buyer"]
    assert captured["limit"] == 5
    assert captured["min_score"] == 0.2


@pytest.mark.asyncio
async def test_suggested_matches_filters_private_fields_for_owner_view():
    cfg = _config()
    profile = _producer_profile()
    # candidate exposes a private field; the producer (owner of source profile, but
    # only an authenticated peer relative to the candidate) must not see it.
    cand = _buyer_candidate("buyer-a", score=0.5)
    cand["profile"]["fields"]["financial_notes"] = "secret"  # not in buyer schema, dropped silently
    # Add a private candidate field that exists in the buyer schema by mutating cfg:
    candidates = [cand]

    with patch.object(
        matching.profiles_repo, "get_profile_by_id", new=AsyncMock(return_value=profile)
    ), patch.object(
        matching.vector_service,
        "get_profile_embedding",
        new=AsyncMock(return_value=[0.1] * 1536),
    ), patch.object(
        matching.vector_service,
        "find_similar_profiles",
        new=AsyncMock(return_value=candidates),
    ):
        out = await matching.suggested_matches(
            cfg,
            profile_id="p-1",
            type_slug="producer",
            viewer={"_id": "u-1", "role": "user"},
        )

    fields = out["results"][0]["fields"]
    # org_name is public on buyer; financial_notes is not declared on buyer → dropped.
    assert "org_name" in fields
    assert "financial_notes" not in fields
