from pydantic import BaseSettings, AnyHttpUrl
import os
from dotenv import load_dotenv
load_dotenv()

class Settings(BaseSettings):   
    # rabbitmq_url: str
    # asset_service_url: AnyHttpUrl
    # llm_orchestration_service_url: AnyHttpUrl

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://mongodb:27017")
        DB_NAME: str = os.getenv("DB_NAME", "assets_db")
        RABBITMQ_URL: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
        S3_ENDPOINT: str = os.getenv("S3_ENDPOINT", "http://s3-server:9000")
        S3_BUCKET: str = os.getenv("ASSETS_BUCKET", os.getenv("S3_BUCKET", "assets"))
        S3_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        S3_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")


settings = Settings()