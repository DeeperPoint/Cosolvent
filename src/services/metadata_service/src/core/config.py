from pydantic import BaseSettings, AnyHttpUrl


class Settings(BaseSettings):
    rabbitmq_url: str
    asset_service_url: AnyHttpUrl
    llm_orchestration_service_url: AnyHttpUrl

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()