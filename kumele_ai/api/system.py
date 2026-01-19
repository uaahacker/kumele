"""
System Router - Health checks and monitoring
"""
from fastapi import APIRouter, Depends
from datetime import datetime
import redis
from kumele_ai.config import settings
from kumele_ai.services.llm_service import llm_service
from kumele_ai.services.translate_service import translate_service
from kumele_ai.services.chatbot_service import chatbot_service

router = APIRouter()


@router.get("/ai/health")
async def health_check():
    """
    Health check endpoint returning status of all services.
    Returns machine-readable JSON with exact contract.
    """
    # Check Redis
    redis_status = "unhealthy"
    worker_queue_depth = 0
    try:
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        redis_status = "healthy"
        # Get queue depth (Celery default queue)
        worker_queue_depth = r.llen("celery") or 0
    except Exception:
        pass
    
    # Check Qdrant
    qdrant_status = "unhealthy"
    try:
        if await chatbot_service.health_check():
            qdrant_status = "healthy"
    except Exception:
        pass
    
    # Check Mistral LLM
    mistral_status = "unhealthy"
    try:
        if await llm_service.health_check():
            mistral_status = "healthy"
    except Exception:
        pass
    
    # Check Argos/LibreTranslate
    argos_status = "unhealthy"
    try:
        if await translate_service.health_check():
            argos_status = "healthy"
    except Exception:
        pass
    
    return {
        "redis": redis_status,
        "qdrant": qdrant_status,
        "mistral": mistral_status,
        "argos": argos_status,
        "worker_queue_depth": worker_queue_depth,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
