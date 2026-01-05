"""
System Health and Monitoring API endpoints.

=============================================================================
AI SYSTEM HEALTH (Section 3J of Requirements)
=============================================================================

Overview:
Comprehensive health monitoring for all AI/ML system components.
Used by load balancers, monitoring tools, and admin dashboards.

Components Monitored:
1. Database (PostgreSQL): Connection + pool status
2. Redis: Cache/queue connectivity
3. Qdrant: Vector DB status
4. LLM Services (3-tier fallback):
   - Internal TGI (self-hosted)
   - Mistral API (external)
   - OpenRouter (free fallback)
5. ML Models: HuggingFace model availability

Health Status:
- healthy: All critical components working
- degraded: Non-critical failures (e.g., 1 LLM down)
- unhealthy: Critical component failure

Response Format:
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "components": {
    "database": {"status": "healthy", "latency_ms": 5},
    "redis": {"status": "healthy"},
    "llm": {"status": "healthy", "provider": "mistral_api"}
  },
  "system": {"cpu": 45.2, "memory": 68.5}
}

Endpoints:
- GET /ai/health: Full health check (all components)
- GET /ai/health/quick: Fast check (DB + Redis only)
- GET /ai/metrics: Prometheus-compatible metrics
- GET /ai/models: List loaded ML models
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.database import get_db
from app.services.system_service import SystemService
from app.schemas.schemas import SystemHealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["System"])


@router.get(
    "/health",
    response_model=SystemHealthResponse,
    summary="AI System Health Check",
    description="""
    Comprehensive health check for all AI/ML system components.
    
    Checks:
    - **Database**: PostgreSQL connection
    - **Redis**: Cache/queue connection
    - **Qdrant**: Vector database for embeddings
    - **LLM**: Language model service (TGI/Mistral)
    - **Translation**: LibreTranslate service
    
    System metrics:
    - CPU usage
    - Memory usage
    - Disk usage
    
    Returns overall status:
    - healthy: All components operational
    - degraded: Some components have issues
    - unhealthy: Critical components down
    """
)
async def health_check(
    db: AsyncSession = Depends(get_db)
):
    """Get full system health status."""
    try:
        result = await SystemService.get_full_health(db)
        return result
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@router.get(
    "/health/simple",
    summary="Simple Health Check",
    description="Simple health check for load balancers. Returns 200 if healthy."
)
async def simple_health(
    db: AsyncSession = Depends(get_db)
):
    """Simple health check."""
    try:
        result = await SystemService.get_simple_health(db)
        
        if result["status"] != "healthy":
            raise HTTPException(status_code=503, detail=result)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get(
    "/metrics",
    summary="System Metrics",
    description="Get Prometheus-style metrics for monitoring."
)
async def get_metrics():
    """Get system metrics."""
    try:
        result = await SystemService.get_metrics()
        return result
        
    except Exception as e:
        logger.error(f"Get metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/health/db",
    summary="Database Health",
    description="Check database connectivity."
)
async def db_health(
    db: AsyncSession = Depends(get_db)
):
    """Check database health."""
    try:
        result = await SystemService.check_database(db)
        return result
        
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get(
    "/health/qdrant",
    summary="Qdrant Health",
    description="Check Qdrant vector database connectivity."
)
async def qdrant_health():
    """Check Qdrant health."""
    try:
        result = await SystemService.check_qdrant()
        return result
        
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get(
    "/health/llm",
    summary="LLM Health",
    description="Check LLM service connectivity."
)
async def llm_health():
    """Check LLM health."""
    try:
        result = await SystemService.check_llm()
        return result
        
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get(
    "/models",
    summary="List AI Models",
    description="""
    List all registered AI/ML models.
    
    Returns:
    - Model name and type
    - Status (loaded/inactive)
    - Provider (huggingface, tgi, argos, etc.)
    
    Foundation-ready endpoint.
    """
)
async def list_ai_models(
    db: AsyncSession = Depends(get_db)
):
    """List registered AI models."""
    try:
        result = await SystemService.get_ai_models(db)
        return result
        
    except Exception as e:
        logger.error(f"List models error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/reload-model",
    summary="Reload AI Model",
    description="""
    Reload/refresh an AI model.
    
    Use cases:
    - Force model cache refresh
    - Apply model updates
    - Reset model state
    
    Foundation-ready endpoint.
    """
)
async def reload_model(
    model_name: str
):
    """Reload an AI model."""
    try:
        result = await SystemService.reload_model(model_name)
        return result
        
    except Exception as e:
        logger.error(f"Reload model error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/stats",
    summary="AI System Statistics",
    description="""
    Get AI system usage statistics.
    
    Returns:
    - AI action counts (24h)
    - Chatbot query counts (24h)
    - Worker queue depth
    - System metrics
    
    Foundation-ready endpoint.
    """
)
async def get_ai_stats(
    db: AsyncSession = Depends(get_db)
):
    """Get AI system statistics."""
    try:
        result = await SystemService.get_ai_stats(db)
        return result
        
    except Exception as e:
        logger.error(f"Get AI stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

