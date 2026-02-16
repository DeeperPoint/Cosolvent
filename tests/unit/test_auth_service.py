"""Tests for auth service security/error handling."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError
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
