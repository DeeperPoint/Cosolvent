"""Tests for app.core.config.Settings validation (GAP-1 cookie/CORS knobs)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_default_samesite_is_lax():
    assert Settings().session_cookie_samesite == "lax"


@pytest.mark.parametrize("value", ["lax", "Lax", "STRICT", "None"])
def test_samesite_accepts_known_values_case_insensitively(value: str):
    s = Settings(session_cookie_samesite=value, session_cookie_secure=True)
    assert s.session_cookie_samesite == value.lower()


def test_samesite_rejects_unknown_value():
    with pytest.raises(ValidationError, match="session_cookie_samesite"):
        Settings(session_cookie_samesite="whatever")


def test_samesite_none_requires_secure_cookie():
    with pytest.raises(ValidationError, match="requires session_cookie_secure"):
        Settings(session_cookie_samesite="none", session_cookie_secure=False)


def test_samesite_none_with_secure_is_valid():
    s = Settings(session_cookie_samesite="none", session_cookie_secure=True)
    assert s.session_cookie_samesite == "none"
    assert s.session_cookie_secure is True


def test_samesite_lax_does_not_require_secure():
    s = Settings(session_cookie_samesite="lax", session_cookie_secure=False)
    assert s.session_cookie_samesite == "lax"
