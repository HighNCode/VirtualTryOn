"""
Configuration Management
Handles all environment variables and application settings
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_NAME: str = "Virtual Try-On API"
    APP_VERSION: str = "1.0.0"
    SECRET_KEY: str = "dev-secret-key-change-in-production"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "postgresql://dev:dev123@localhost:5432/virtual_tryon_dev"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 50
    IMAGE_CACHE_TTL: int = 86400  # 24 hours
    STUDIO_CACHE_TTL: int = 3600  # 1 hour for studio look results
    SESSION_TTL: int = 86400  # 24 hours

    # Shopify
    SHOPIFY_API_KEY: Optional[str] = None
    SHOPIFY_API_SECRET: Optional[str] = None
    SHOPIFY_SCOPES: str = "read_products,write_script_tags"
    SHOPIFY_API_VERSION: str = "2024-01"

    # Google Vertex AI (Gemini image generation)
    GOOGLE_CLOUD_PROJECT: Optional[str] = None
    GOOGLE_CLOUD_LOCATION: str = "us-central1"
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None   # Path to service account JSON
    TRYON_MODEL: str = "gemini-2.5-flash-image"               # Switchable via env var; must support image output

    # Admin
    ADMIN_API_KEY: str = "change-this-admin-key-in-production"

    # Security
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"
    ALLOWED_UPLOAD_EXTENSIONS: str = "jpg,jpeg,png,webp"
    MAX_UPLOAD_SIZE: int = 10485760  # 10MB in bytes

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60

    # Performance
    MEASUREMENT_TIMEOUT: int = 10  # seconds
    TRYON_TIMEOUT: int = 120  # seconds

    # SMPL Body Measurement Pipeline
    SMPL_MODEL_DIR: str = "data/body_models"
    HMR_CHECKPOINT_DIR: str = "data/checkpoints"
    REGRESSOR_BACKEND: str = "shapy"  # "hmr2" or "shapy"

    class Config:
        env_file = ".env"
        case_sensitive = True


# Singleton instance
settings = Settings()


def get_settings() -> Settings:
    """Get settings instance"""
    return settings
