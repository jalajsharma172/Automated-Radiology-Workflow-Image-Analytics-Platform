import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "MedVision AI"
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/medvision")
    
    # Redis / Celery
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Storage (AWS S3 / MinIO)
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")
    # Default to localhost for local dev outside docker. Inside docker, docker-compose overrides this.
    AWS_ENDPOINT_URL: str = os.getenv("AWS_ENDPOINT_URL", "http://localhost:9000") 
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "medvision-data")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")

    class Config:
        env_file = ".env"

settings = Settings()
