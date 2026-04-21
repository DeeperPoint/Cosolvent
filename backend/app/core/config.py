from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings


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
    session_ttl_hours: int = 72
    # When False, Set-Cookie omits Secure (needed for HTTP clients e.g. httpx integration tests on localhost).
    # Production behind HTTPS should set SESSION_COOKIE_SECURE=true (default).
    session_cookie_secure: bool = True

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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
