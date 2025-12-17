"""
Configuration module for Kumele AI/ML Service
Loads environment variables and provides settings
"""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_ENV: str = "development"
    APP_DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"
    API_KEY: str = "internal-api-key"
    
    # Database
    DATABASE_URL: str = "postgresql://kumele:kumele@postgres:5432/kumele_ai"
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Qdrant
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_COLLECTION: str = "knowledge_embeddings"
    
    # Translation Service (Argos/LibreTranslate)
    TRANSLATE_URL: str = "http://argos:5000"
    
    # LLM Configuration
    # Provider: "local" (TGI/Mistral), "openrouter", or "auto" (try local, fallback to openrouter)
    LLM_PROVIDER: str = "auto"
    
    # Local LLM (Mistral via TGI) - used when LLM_PROVIDER is "local" or "auto"
    LLM_API_URL: str = "http://mistral:8080"
    LLM_MODEL: str = "mistralai/Mistral-7B-Instruct-v0.2"
    
    # OpenRouter - used when LLM_PROVIDER is "openrouter" or as fallback in "auto" mode
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_API_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "mistralai/mistral-7b-instruct"  # or "meta-llama/llama-3.1-8b-instruct"
    OPENROUTER_SITE_URL: str = "https://kumele.ai"  # For OpenRouter rankings
    OPENROUTER_SITE_NAME: str = "Kumele"
    
    # SMTP (Acelle)
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    SMTP_FROM_EMAIL: str = "support@kumele.ai"
    
    # Embedding model
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    # Moderation thresholds
    MODERATION_TEXT_TOXICITY_THRESHOLD: float = 0.60
    MODERATION_TEXT_HATE_THRESHOLD: float = 0.30
    MODERATION_TEXT_SPAM_THRESHOLD: float = 0.70
    MODERATION_IMAGE_NUDITY_THRESHOLD: float = 0.60
    MODERATION_IMAGE_VIOLENCE_THRESHOLD: float = 0.50
    MODERATION_IMAGE_HATE_THRESHOLD: float = 0.40
    
    # Nominatim Geocoding
    NOMINATIM_URL: str = "https://nominatim.openstreetmap.org"
    NOMINATIM_USER_AGENT: str = "KumeleAI/1.0 (support@kumele.ai)"
    NOMINATIM_TIMEOUT_SEC: int = 10
    NOMINATIM_CACHE_TTL_SEC: int = 86400
    
    # Celery
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"
    
    class Config:
        env_file = ".env"
        extra = "allow"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
