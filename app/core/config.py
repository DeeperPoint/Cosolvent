from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "cosolvent"

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

    # Pinecone
    pinecone_api_key: str = ""
    pinecone_index: str = "cosolvent"

    # Cohere
    cohere_api_key: str = ""

    # Email
    resend_api_key: str = ""
    email_from: str = "noreply@example.com"

    # App
    marketplace_config_path: str = "marketplace.yaml"
    cors_origins: list[str] = ["http://localhost:3000"]
    debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
