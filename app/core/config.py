from __future__ import annotations

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

    # S3
    s3_bucket: str = "cosolvent-files"
    s3_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # OpenAI
    openai_api_key: str = ""

    # Cohere
    cohere_api_key: str = ""

    # Email
    resend_api_key: str = ""
    email_from: str = "noreply@example.com"

    # App
    marketplace_config_path: str = "marketplace.yaml"
    cors_origins: list[str] = ["http://localhost:3000"]
    debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
