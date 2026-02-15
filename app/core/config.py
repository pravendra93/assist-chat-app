import os
from typing import Optional, List, Union
try:
    from pydantic_settings import BaseSettings
    from pydantic import validator
except ImportError:
    from pydantic import BaseSettings, validator

class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "local")
    
    # ... other settings can be added here as needed ...
    
    # Email Settings
    EMAIL_PROVIDER: str = os.getenv("EMAIL_PROVIDER") # Options: console, ses, sendgrid, smtp
    EMAIL_FROM: str = os.getenv("EMAIL_FROM")
    
    # AWS SES
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_REGION: str = "us-east-1"
    
    # SendGrid
    SENDGRID_API_KEY: Optional[str] = os.getenv("SENDGRID_API_KEY")

    # Resend
    RESEND_API_KEY: Optional[str] = os.getenv("RESEND_API_KEY")
    
    # SMTP
    SMTP_HOST: Optional[str] = os.getenv("SMTP_HOST")
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = os.getenv("SMTP_USER")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    SMTP_TLS: bool = True
    
    # AI / Embeddings
    OPENAI_API_KEY: Optional[str] = os.getenv("OPEN_AI_KEY")

    # Celery
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND")

    # Digital Ocean Spaces / S3
    SPACES_ACCESS_KEY_ID: Optional[str] = os.getenv("SPACES_ACCESS_KEY_ID")
    SPACES_SECRET_ACCESS_KEY: Optional[str] = os.getenv("SPACES_SECRET_ACCESS_KEY")
    SPACES_REGION: str = os.getenv("SPACES_REGION", "sgp1")
    SPACES_BUCKET: str = os.getenv("SPACES_BUCKET", "dev-assistra")
    SPACES_ENDPOINT: str = os.getenv("SPACES_ENDPOINT", "https://sgp1.digitaloceanspaces.com")

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = os.getenv("BACKEND_CORS_ORIGINS", "[]")

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
