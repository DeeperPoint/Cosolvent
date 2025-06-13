from pydantic import BaseSettings

class Settings(BaseSettings):
    rabbitmq_url: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
