"""Tests for auth HTTP cookie/session response behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.dependencies import get_config
from app.core.exceptions import register_exception_handlers
from app.modules.auth.router import router


def _auth_result(token: str = "token-123") -> dict:
    return {
        "user_id": "u1",
        "email": "user@example.com",
        "participant_type": "producer",
        "role": "user",
        "has_onboarded": False,
        "session_token": token,
    }


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    mock_config = MagicMock()
    mock_config.auth.allow_public_signup = True
    app.include_router(router, prefix="/api/auth")
    app.dependency_overrides[get_config] = lambda: mock_config
    return TestClient(app)


@pytest.fixture
def client_signup_disabled() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    mock_config = MagicMock()
    mock_config.auth.allow_public_signup = False
    app.include_router(router, prefix="/api/auth")
    app.dependency_overrides[get_config] = lambda: mock_config
    return TestClient(app)


@pytest.mark.parametrize(
    "path,payload,service_fn,expected_status",
    [
        ("/api/auth/signup", {"email": "user@example.com", "password": "Password123!", "participant_type": "producer"}, "signup", 201),
        ("/api/auth/login", {"email": "user@example.com", "password": "Password123!"}, "login", 200),
        ("/api/auth/bootstrap", {"email": "admin@example.com", "password": "Password123!"}, "bootstrap_admin", 200),
    ],
)
def test_auth_endpoints_hide_token_and_set_secure_cookie(client: TestClient, path: str, payload: dict, service_fn: str, expected_status: int):
    with patch(
        f"app.modules.auth.router.service.{service_fn}",
        new=AsyncMock(return_value=_auth_result()),
    ):
        response = client.post(path, json=payload)

    assert response.status_code == expected_status
    assert "session_token" not in response.json()

    cookie = response.headers["set-cookie"]
    assert "session_token=token-123" in cookie
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie
    assert f"Max-Age={settings.session_ttl_hours * 60 * 60}" in cookie


def test_signup_returns_403_when_public_signup_disabled(client_signup_disabled: TestClient):
    response = client_signup_disabled.post(
        "/api/auth/signup",
        json={"email": "user@example.com", "password": "Password123!", "participant_type": "producer"},
    )
    assert response.status_code == 403
    assert "disabled" in response.json().get("detail", "").lower()


def test_logout_deletes_cookie_with_secure_flags(client: TestClient):
    with patch("app.modules.auth.router.service.logout", new=AsyncMock()) as logout_mock:
        client.cookies.set("session_token", "token-123")
        response = client.post("/api/auth/logout")

    assert response.status_code == 200
    logout_mock.assert_awaited_once_with("token-123")

    cookie = response.headers["set-cookie"]
    assert "session_token=" in cookie
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie
    assert "Max-Age=0" in cookie
