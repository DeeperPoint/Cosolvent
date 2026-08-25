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
    "path,payload,service_fn",
    [
        ("/api/auth/signup", {"email": "user@example.com", "password": "Password123!", "participant_type": "producer"}, "signup"),
        ("/api/auth/login", {"email": "user@example.com", "password": "Password123!"}, "login"),
        ("/api/auth/bootstrap", {"email": "admin@example.com", "password": "Password123!"}, "bootstrap_admin"),
    ],
)
def test_auth_endpoints_expose_bearer_token_and_set_secure_cookie(client: TestClient, path: str, payload: dict, service_fn: str):
    """The raw `session_token` key never appears (internal name). It is re-exposed as
    `access_token` — the bearer credential cross-origin/native callers use (GAP-1) —
    but only when the caller opts in with `X-Auth-Mode: bearer`, so a same-origin
    browser client never receives the session token in a JS-readable form. The cookie
    is set either way."""
    with patch(
        f"app.modules.auth.router.service.{service_fn}",
        new=AsyncMock(return_value=_auth_result()),
    ):
        response = client.post(path, json=payload)
        opted_in = client.post(path, json=payload, headers={"X-Auth-Mode": "bearer"})

    assert response.status_code == 200
    body = response.json()
    assert "session_token" not in body
    # Default: no usable token handed to page scripts.
    assert body.get("access_token") is None
    # Opt-in: the bearer credential is returned for callers that cannot use cookies.
    assert opted_in.json()["access_token"] == "token-123"

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


def test_logout_accepts_bearer_token_with_no_cookie(client: TestClient):
    """A cross-origin/native caller with no cookie jar (GAP-1) can still log out by
    sending the access_token back as a Bearer header."""
    with patch("app.modules.auth.router.service.logout", new=AsyncMock()) as logout_mock:
        response = client.post(
            "/api/auth/logout", headers={"Authorization": "Bearer token-123"}
        )

    assert response.status_code == 200
    logout_mock.assert_awaited_once_with("token-123")


def test_logout_prefers_bearer_token_over_stale_cookie(client: TestClient):
    with patch("app.modules.auth.router.service.logout", new=AsyncMock()) as logout_mock:
        client.cookies.set("session_token", "cookie-token")
        response = client.post(
            "/api/auth/logout", headers={"Authorization": "Bearer header-token"}
        )

    assert response.status_code == 200
    logout_mock.assert_awaited_once_with("header-token")


def test_session_cookie_samesite_is_configurable(client: TestClient):
    """A cross-origin sponsor frontend needs SameSite=None (GAP-1); confirm it's actually
    honored end-to-end rather than the hardcoded "lax" this replaced."""
    with patch(
        "app.modules.auth.router.service.login",
        new=AsyncMock(return_value=_auth_result()),
    ), patch.object(settings, "session_cookie_samesite", "none"):
        response = client.post(
            "/api/auth/login", json={"email": "user@example.com", "password": "Password123!"}
        )

    cookie = response.headers["set-cookie"]
    assert "samesite=none" in cookie.lower()


# ── demo persona assignment ──────────────────────────────────────────────────

def _persona_result() -> dict:
    return {**_auth_result(), "persona": {"profile_id": "p1", "participant_type": "producer", "fields": {}}}


def test_demo_persona_403s_when_demo_mode_off(client: TestClient):
    with patch.object(settings, "demo_mode", "off"):
        response = client.post("/api/auth/demo-persona", json={"participant_type": "producer"})
    assert response.status_code == 403
    assert "demo mode" in response.json()["detail"].lower()


def test_demo_persona_logs_in_and_returns_persona(client: TestClient):
    with patch.object(settings, "demo_mode", "showcase"), patch(
        "app.modules.auth.router.service.assign_demo_persona",
        new=AsyncMock(return_value=_persona_result()),
    ):
        response = client.post("/api/auth/demo-persona", json={"participant_type": "producer"})

    assert response.status_code == 200
    body = response.json()
    # Opt-in only (GAP-1): the demo UI is same-origin and uses the cookie.
    assert body.get("access_token") is None
    assert body["persona"] == {"profile_id": "p1", "participant_type": "producer", "fields": {}}
    assert "session_token=token-123" in response.headers["set-cookie"]
