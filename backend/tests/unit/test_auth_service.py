"""Tests for auth service security/error handling."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError
from app.modules.auth import service


class _Config:
    def get_type(self, slug: str):
        if slug == "producer":
            return object()
        return None


def _integrity_error(constraint: str) -> IntegrityError:
    return IntegrityError(
        "insert users",
        {},
        Exception(f'duplicate key value violates unique constraint "{constraint}"'),
    )


@pytest.mark.asyncio
async def test_signup_maps_unique_email_violation_to_conflict():
    with patch("app.modules.auth.service.repo") as mock_repo, patch(
        "app.modules.auth.service.hash_password", return_value="hashed"
    ):
        mock_repo.find_user_by_email = AsyncMock(return_value=None)
        mock_repo.create_user = AsyncMock(side_effect=_integrity_error("uq_users_email"))

        with pytest.raises(ConflictError, match="Email already registered"):
            await service.signup("user@example.com", "Password123!", "producer", _Config())


@pytest.mark.asyncio
async def test_bootstrap_maps_singleton_conflict_to_conflict_error():
    with patch("app.modules.auth.service.repo") as mock_repo, patch(
        "app.modules.auth.service.hash_password", return_value="hashed"
    ):
        mock_repo.count_admins = AsyncMock(return_value=0)
        mock_repo.create_user = AsyncMock(
            side_effect=_integrity_error("uq_users_bootstrap_marker")
        )

        with pytest.raises(ConflictError, match="Admin already exists"):
            await service.bootstrap_admin("admin@example.com", "Password123!")


@pytest.mark.asyncio
async def test_bootstrap_sets_marker_on_admin_user_creation():
    with patch("app.modules.auth.service.repo") as mock_repo, patch(
        "app.modules.auth.service.hash_password", return_value="hashed"
    ):
        mock_repo.count_admins = AsyncMock(return_value=0)
        mock_repo.create_user = AsyncMock(
            return_value={
                "_id": "u1",
                "email": "admin@example.com",
                "role": "admin",
                "participant_type": None,
                "has_onboarded": False,
            }
        )
        mock_repo.create_session = AsyncMock(return_value="token")

        await service.bootstrap_admin("admin@example.com", "Password123!")

        mock_repo.create_user.assert_awaited_once()
        assert mock_repo.create_user.await_args.kwargs["bootstrap_marker"] == "primary-admin"


@pytest.mark.asyncio
async def test_login_rejects_when_no_password_hash():
    with patch("app.modules.auth.service.repo") as mock_repo:
        mock_repo.find_user_by_email = AsyncMock(
            return_value={"_id": "u1", "email": "a@b.com"}
        )

        with pytest.raises(UnauthorizedError, match="No password set"):
            await service.login("a@b.com", "anything")


# ── demo persona assignment ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_demo_persona_rejects_unknown_participant_type():
    with pytest.raises(NotFoundError, match="Unknown participant type"):
        await service.assign_demo_persona("ghost", _Config())


@pytest.mark.asyncio
async def test_demo_persona_rejects_when_no_synthetic_profiles_exist():
    real_only = [{"user_id": "u1", "is_synthetic": False, "fields": {}}]
    with patch("app.modules.profiles.repository.list_profiles", new=AsyncMock(return_value=real_only)):
        with pytest.raises(NotFoundError, match="No synthetic producer personas"):
            await service.assign_demo_persona("producer", _Config())


@pytest.mark.asyncio
async def test_demo_persona_never_picks_a_real_profile():
    """Even mixed in with real profiles, only is_synthetic=True is ever eligible."""
    mixed = [
        {"_id": "p-real", "user_id": "u-real", "is_synthetic": False, "fields": {"x": 1}},
        {"_id": "p-real2", "user_id": "u-real2", "is_synthetic": False, "fields": {"x": 2}},
    ]
    with patch("app.modules.profiles.repository.list_profiles", new=AsyncMock(return_value=mixed)):
        with pytest.raises(NotFoundError, match="No synthetic"):
            await service.assign_demo_persona("producer", _Config())


@pytest.mark.asyncio
async def test_demo_persona_logs_in_as_the_synthetic_profiles_owner():
    synthetic = [{"_id": "p1", "user_id": "u1", "is_synthetic": True, "fields": {"farm_name": "Farm A"}}]
    user = {"_id": "u1", "email": "synthetic+p1@population.local", "role": "user",
            "participant_type": "producer", "has_onboarded": True}
    with patch("app.modules.profiles.repository.list_profiles", new=AsyncMock(return_value=synthetic)), \
         patch("app.modules.auth.service.repo") as mock_repo:
        mock_repo.find_user_by_id = AsyncMock(return_value=user)
        mock_repo.create_session = AsyncMock(return_value="tok-123")

        result = await service.assign_demo_persona("producer", _Config())

    assert result["user_id"] == "u1"
    assert result["session_token"] == "tok-123"
    assert result["persona"] == {
        "profile_id": "p1", "participant_type": "producer", "fields": {"farm_name": "Farm A"}
    }
    mock_repo.find_user_by_id.assert_awaited_once_with("u1")


@pytest.mark.asyncio
async def test_demo_persona_404s_if_owning_user_is_missing():
    synthetic = [{"_id": "p1", "user_id": "orphan", "is_synthetic": True, "fields": {}}]
    with patch("app.modules.profiles.repository.list_profiles", new=AsyncMock(return_value=synthetic)), \
         patch("app.modules.auth.service.repo") as mock_repo:
        mock_repo.find_user_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError, match="Persona's user account not found"):
            await service.assign_demo_persona("producer", _Config())
