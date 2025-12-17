from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",   # ✅ THIS FIXES THE CRASH
        case_sensitive=True
    )

    # General
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    SECRET_KEY: str = "your-secret-key-change-in-production"
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Qdrant
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_COLLECTION: str = "kumele_knowledge"

    # Translation
    TRANSLATE_URL: str = "http://libretranslate:5000"
    SUPPORTED_LANGUAGES: list[str] = ["en", "fr", "es", "zh", "ar", "de"]

    # LLM Configuration (supports internal TGI, external Mistral API, and OpenRouter)
    # Option 1: Internal TGI server (same server/network)
    LLM_API_URL: str = "http://tgi:80"
    LLM_MODEL: str = "mistralai/Mistral-7B-Instruct-v0.2"
    
    # Option 2: External Mistral API (different server)
    MISTRAL_API_KEY: Optional[str] = None  # Set this to use Mistral's hosted API
    MISTRAL_API_URL: str = "https://api.mistral.ai/v1"
    MISTRAL_MODEL: str = "mistral-small-latest"  # or mistral-medium, mistral-large
    
    # Option 3: OpenRouter (free Mistral and other models)
    OPENROUTER_API_KEY: Optional[str] = None  # Set this to use OpenRouter
    OPENROUTER_API_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "mistralai/mistral-7b-instruct:free"  # Free Mistral on OpenRouter
    
    # LLM Mode: "internal" (TGI), "external" (Mistral API), or "openrouter"
    LLM_MODE: str = "internal"  # Change to "external" or "openrouter"

    # Models
    SENTIMENT_MODEL: str
    EMBEDDING_MODEL: str
    MODERATION_MODEL: str
    IMAGE_MODERATION_MODEL: str = "Falconsai/nsfw_image_detection"

    # Email
    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USER: str
    SMTP_PASS: str

    # Celery
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # Ratings
    RATING_ATTENDEE_WEIGHT: float = 0.7
    RATING_SYSTEM_WEIGHT: float = 0.3

    # Moderation thresholds
    TOXICITY_THRESHOLD: float = 0.60
    HATE_THRESHOLD: float = 0.30
    SPAM_THRESHOLD: float = 0.70
    NUDITY_THRESHOLD: float = 0.60
    VIOLENCE_THRESHOLD: float = 0.50
    HATE_SYMBOLS_THRESHOLD: float = 0.40

    # CORS
    CORS_ORIGINS: list[str] = ["*"]
    
    # Image Processing
    IMAGE_ANALYSIS_ENABLED: bool = True  # Enable HuggingFace image analysis


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
