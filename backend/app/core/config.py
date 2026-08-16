from __future__ import annotations

from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings

SameSitePolicy = Literal["lax", "strict", "none"]


class Settings(BaseSettings):
    # Postgres
    postgres_dsn: str = ""
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "cosolvent"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Session
    session_secret: str = "change-me"
    # Shared HMAC key for the synthetic-population watermark (GAP-9). ClientSynth
    # signs synthetic records with this same secret; the ingest boundary verifies it.
    synthetic_watermark_secret: str = "change-me-synthetic"
    session_ttl_hours: int = 72
    # When False, the session cookie omits the Secure flag so it is stored over
    # plain http from any host (127.0.0.1, LAN IPs). Keep True in production.
    session_cookie_secure: bool = True
    # SameSite policy for the session cookie. "lax" (default) is correct for a
    # same-origin deployment (frontend and API behind one reverse-proxy origin).
    # A sponsor frontend on a genuinely different origin (GAP-1 — the headless model
    # is the product) needs "none", which browsers only honor alongside Secure=true;
    # the validator below enforces that pairing. Cross-origin callers that can't rely
    # on third-party cookies at all (native apps, server-to-server) should use the
    # `access_token` bearer credential returned alongside the cookie instead — see
    # auth/router.py.
    session_cookie_samesite: SameSitePolicy = "lax"

    # S3
    s3_bucket: str = "cosolvent-files"
    s3_region: str = "us-east-1"
    s3_endpoint_url: str | None = None
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    files_max_upload_bytes: int = 26_214_400
    files_private_url_ttl_seconds: int = 300
    files_allowed_privacy: list[str] = ["public", "private"]

    # OpenAI
    openai_api_key: str = ""

    # OpenRouter
    openrouter_api_key: str = ""

    # Google Gemini
    gemini_api_key: str = ""

    # Cohere
    cohere_api_key: str = ""

    # Email
    resend_api_key: str = ""
    email_from: str = "noreply@example.com"

    # App
    marketplace_config_path: str = "marketplace.yaml"
    cors_origins: list[str] = ["http://localhost:3000"]
    debug: bool = False

    # Demo Mode staging (MarketForge Phase 6a / story-progression §11 mode note):
    #   off      — normal marketplace (writes allowed, live AI).
    #   showcase — Mode 1: read-only, no DB writes, no live AI (pre-computed/cached only).
    #   live     — Mode 2: writes allowed but sessions are meant to be ephemeral (stateless).
    #   full     — Mode 3: fully stateful — the async acknowledgment lifecycle is live.
    demo_mode: str = "off"

    # If set, overrides marketplace.yaml `auth.allow_public_signup` (e.g. ALLOW_PUBLIC_SIGNUP=true for integration tests)
    allow_public_signup: bool | None = None
    # If set, overrides marketplace.yaml `auth.allow_public_application`
    allow_public_application: bool | None = None

    @field_validator("allow_public_signup", "allow_public_application", mode="before")
    @classmethod
    def _empty_public_signup_to_none(cls, v: object) -> object:
        if v == "":
            return None
        return v

    @field_validator("session_cookie_samesite", mode="before")
    @classmethod
    def _normalize_samesite(cls, v: object) -> object:
        # Lowercase before the Literal check below runs, so `SESSION_COOKIE_SAMESITE=None`
        # (a natural env-var spelling) validates the same as `none`.
        return v.lower() if isinstance(v, str) else v

    @model_validator(mode="after")
    def _samesite_none_requires_secure(self) -> "Settings":
        # Browsers silently reject `SameSite=None` cookies that aren't also `Secure` —
        # this would reproduce GAP-1's "fails silently" symptom one config knob later.
        if self.session_cookie_samesite == "none" and not self.session_cookie_secure:
            raise ValueError(
                "session_cookie_samesite='none' requires session_cookie_secure=true "
                "(browsers drop SameSite=None cookies that aren't Secure)"
            )
        return self

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
