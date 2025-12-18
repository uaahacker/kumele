"""
Kumele AI/ML Backend Configuration.

Centralized configuration management using Pydantic Settings.

Environment Variables:
======================
All settings can be overridden via environment variables or .env file.

Required:
---------
- DATABASE_URL: PostgreSQL connection string
- REDIS_URL: Redis connection string
- SENTIMENT_MODEL: HuggingFace model for sentiment analysis
- EMBEDDING_MODEL: HuggingFace model for embeddings
- MODERATION_MODEL: HuggingFace model for text moderation
- SMTP_HOST/PORT/USER/PASS: Email configuration
- CELERY_BROKER_URL/RESULT_BACKEND: Celery configuration

Optional LLM Configuration (3-tier fallback):
---------------------------------------------
1. Internal TGI (self-hosted):
   - LLM_API_URL: Internal TGI endpoint (default: http://tgi:80)
   
2. External Mistral API:
   - MISTRAL_API_KEY: Your Mistral API key
   - MISTRAL_MODEL: Model to use (default: mistral-small-latest)
   
3. OpenRouter (free fallback):
   - OPENROUTER_API_KEY: Your OpenRouter API key
   - OPENROUTER_MODEL: Model to use (default: mistralai/mistral-7b-instruct:free)

Moderation Thresholds:
----------------------
- TOXICITY_THRESHOLD: 0.60 (flag content above this)
- HATE_THRESHOLD: 0.30 (lower = more sensitive)
- NUDITY_THRESHOLD: 0.60 (for image moderation)

Rating Weights:
---------------
- RATING_ATTENDEE_WEIGHT: 0.70 (70% from attendee ratings)
- RATING_SYSTEM_WEIGHT: 0.30 (30% from system metrics)
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings with environment variable support.
    
    Uses Pydantic Settings for automatic env var loading and validation.
    Settings are cached via @lru_cache for performance.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",   # Ignore extra env vars (prevents crashes)
        case_sensitive=True
    )

    # ==========================================================================
    # General Settings
    # ==========================================================================
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    SECRET_KEY: str = "your-secret-key-change-in-production"
    API_V1_PREFIX: str = "/api/v1"

    # ==========================================================================
    # Database (PostgreSQL)
    # ==========================================================================
    DATABASE_URL: str  # Required: postgresql+asyncpg://user:pass@host:5432/db

    # ==========================================================================
    # Cache/Queue (Redis)
    # ==========================================================================
    REDIS_URL: str = "redis://redis:6379/0"

    # ==========================================================================
    # Vector Database (Qdrant) - for RAG chatbot
    # ==========================================================================
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_COLLECTION: str = "kumele_knowledge"

    # ==========================================================================
    # Translation Service
    # ==========================================================================
    TRANSLATE_URL: str = "http://libretranslate:5000"
    SUPPORTED_LANGUAGES: list[str] = ["en", "fr", "es", "zh", "ar", "de"]

    # ==========================================================================
    # LLM Configuration (3-tier fallback: TGI → Mistral → OpenRouter)
    # ==========================================================================
    
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

    # ==========================================================================
    # ML Models (HuggingFace)
    # ==========================================================================
    HUGGINGFACE_API_KEY: Optional[str] = None  # Required for image moderation API
    SENTIMENT_MODEL: str  # e.g., distilbert-base-uncased-finetuned-sst-2-english
    EMBEDDING_MODEL: str  # e.g., sentence-transformers/all-MiniLM-L6-v2
    MODERATION_MODEL: str  # e.g., unitary/toxic-bert
    IMAGE_MODERATION_MODEL: str = "Falconsai/nsfw_image_detection"

    # ==========================================================================
    # Email (SMTP)
    # ==========================================================================
    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USER: str
    SMTP_PASS: str

    # ==========================================================================
    # Celery (Async Task Queue)
    # ==========================================================================
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # ==========================================================================
    # Rating Configuration
    # ==========================================================================
    RATING_ATTENDEE_WEIGHT: float = 0.7  # 70% from user ratings
    RATING_SYSTEM_WEIGHT: float = 0.3    # 30% from system metrics

    # ==========================================================================
    # Moderation Thresholds (0.0 - 1.0)
    # ==========================================================================
    TOXICITY_THRESHOLD: float = 0.60     # General toxicity
    HATE_THRESHOLD: float = 0.30         # Hate speech (lower = more sensitive)
    SPAM_THRESHOLD: float = 0.70         # Spam detection
    NUDITY_THRESHOLD: float = 0.60       # NSFW image detection
    VIOLENCE_THRESHOLD: float = 0.50     # Violence in images
    HATE_SYMBOLS_THRESHOLD: float = 0.40 # Hate symbols in images

    # ==========================================================================
    # CORS
    # ==========================================================================
    CORS_ORIGINS: list[str] = ["*"]
    
    # Image Processing
    IMAGE_ANALYSIS_ENABLED: bool = True  # Enable HuggingFace image analysis


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
