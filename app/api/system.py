"""
System Health and Monitoring API endpoints.
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
