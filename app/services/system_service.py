"""
System Health and Monitoring Service.

Handles AI system health checks and monitoring.

Health Check Components (per requirements Section 3J):
==============================================================================
1. Database (PostgreSQL):
   - Connection test via simple query
   - Connection pool status

2. Cache (Redis):
   - PING/PONG test
   - Memory usage check

3. Vector DB (Qdrant):
   - Collection status
   - Vector count

4. LLM Services (3-tier fallback):
   - Internal TGI: Self-hosted model
   - Mistral API: External paid API
   - OpenRouter: External free fallback
   - Status: healthy if ANY provider works

5. ML Models:
   - HuggingFace model availability
   - Model loading status

Health Response Format:
==============================================================================
{
  "status": "healthy" | "degraded" | "unhealthy",
  "timestamp": "ISO datetime",
  "components": {
    "database": {"status": "healthy", "latency_ms": 5},
    "redis": {"status": "healthy", "latency_ms": 2},
    "qdrant": {"status": "healthy", "collections": 1},
    "llm": {"status": "healthy", "provider": "mistral_api"},
    "ml_models": {"status": "healthy", "loaded": ["embeddings", "sentiment"]}
  },
  "system": {
    "cpu_percent": 45.2,
    "memory_percent": 68.5,
    "disk_percent": 42.0
  }
}

Status Definitions:
==============================================================================
- healthy: All critical components working
- degraded: Some non-critical components failing (e.g., 1 LLM provider down)
- unhealthy: Critical component failure (DB, all LLMs down)

Monitoring Endpoints:
==============================================================================
- GET /system/health: Full health check
- GET /system/health/quick: Fast health check (DB + Redis only)
- GET /system/metrics: Prometheus-compatible metrics
- GET /system/models: List loaded ML models

Alerts:
==============================================================================
- Memory > 90%: Warning
- Disk > 85%: Warning
- Any critical component unhealthy: Critical alert
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime
import logging
import httpx
import asyncio
import psutil
import os
from redis.asyncio import Redis

from app.config import settings

logger = logging.getLogger(__name__)


class SystemService:
    """Service for system health monitoring."""
    
    # Component check timeout
    CHECK_TIMEOUT = 5.0
    
    # Health status thresholds
    CPU_WARNING_THRESHOLD = 80
    MEMORY_WARNING_THRESHOLD = 85
    DISK_WARNING_THRESHOLD = 90

    @staticmethod
    async def check_database(db: AsyncSession) -> Dict[str, Any]:
        """Check PostgreSQL database health."""
        start = datetime.utcnow()
        
        try:
            result = await db.execute(text("SELECT 1"))
            _ = result.scalar()
            
            latency = (datetime.utcnow() - start).total_seconds() * 1000
            
            return {
                "status": "healthy",
                "latency_ms": round(latency, 2),
                "message": "Database connection successful"
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "latency_ms": None,
                "message": str(e)
            }

    @staticmethod
    async def check_redis() -> Dict[str, Any]:
        """Check Redis cache health."""
        start = datetime.utcnow()

        try:
            redis = Redis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=SystemService.CHECK_TIMEOUT,
                socket_timeout=SystemService.CHECK_TIMEOUT,
                decode_responses=True
            )

            await redis.ping()
            await redis.close()

            latency = (datetime.utcnow() - start).total_seconds() * 1000

            return {
                "status": "healthy",
                "latency_ms": round(latency, 2),
                "message": "Redis connection successful"
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "latency_ms": None,
                "message": str(e)
            }

    @staticmethod
    async def check_qdrant() -> Dict[str, Any]:
        """Check Qdrant vector database health."""
        start = datetime.utcnow()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.QDRANT_URL}/",
                    timeout=SystemService.CHECK_TIMEOUT
                )
                
                latency = (datetime.utcnow() - start).total_seconds() * 1000
                
                if response.status_code == 200:
                    return {
                        "status": "healthy",
                        "latency_ms": round(latency, 2),
                        "message": "Qdrant connection successful"
                    }
                else:
                    return {
                        "status": "degraded",
                        "latency_ms": round(latency, 2),
                        "message": f"Qdrant returned status {response.status_code}"
                    }
                    
        except Exception as e:
            return {
                "status": "unhealthy",
                "latency_ms": None,
                "message": str(e)
            }

    @staticmethod
    async def check_llm() -> Dict[str, Any]:
        """Check LLM service health - tries all configured providers."""
        results = {
            "status": "unhealthy",
            "providers": {},
            "active_provider": None,
            "message": "No LLM provider available"
        }
        
        # Check 1: Internal TGI
        if settings.LLM_API_URL:
            start = datetime.utcnow()
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{settings.LLM_API_URL}/health",
                        timeout=SystemService.CHECK_TIMEOUT
                    )
                    latency = (datetime.utcnow() - start).total_seconds() * 1000
                    
                    if response.status_code == 200:
                        results["providers"]["internal_tgi"] = {
                            "status": "healthy",
                            "latency_ms": round(latency, 2),
                            "model": settings.LLM_MODEL
                        }
                        results["status"] = "healthy"
                        results["active_provider"] = "internal_tgi"
                    else:
                        results["providers"]["internal_tgi"] = {
                            "status": "degraded",
                            "latency_ms": round(latency, 2),
                            "error": f"Status {response.status_code}"
                        }
            except Exception as e:
                results["providers"]["internal_tgi"] = {
                    "status": "unhealthy",
                    "error": str(e)[:100]
                }
        
        # Check 2: External Mistral API
        if settings.MISTRAL_API_KEY:
            start = datetime.utcnow()
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{settings.MISTRAL_API_URL}/models",
                        headers={"Authorization": f"Bearer {settings.MISTRAL_API_KEY}"},
                        timeout=SystemService.CHECK_TIMEOUT
                    )
                    latency = (datetime.utcnow() - start).total_seconds() * 1000
                    
                    if response.status_code == 200:
                        results["providers"]["mistral_api"] = {
                            "status": "healthy",
                            "latency_ms": round(latency, 2),
                            "model": settings.MISTRAL_MODEL
                        }
                        if results["status"] != "healthy":
                            results["status"] = "healthy"
                            results["active_provider"] = "mistral_api"
                    else:
                        results["providers"]["mistral_api"] = {
                            "status": "degraded",
                            "latency_ms": round(latency, 2),
                            "error": f"Status {response.status_code}"
                        }
            except Exception as e:
                results["providers"]["mistral_api"] = {
                    "status": "unhealthy",
                    "error": str(e)[:100]
                }
        
        # Check 3: OpenRouter (FREE)
        if settings.OPENROUTER_API_KEY:
            start = datetime.utcnow()
            try:
                async with httpx.AsyncClient() as client:
                    # OpenRouter uses /models endpoint to check API key validity
                    response = await client.get(
                        f"{settings.OPENROUTER_API_URL}/models",
                        headers={
                            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                            "HTTP-Referer": "https://kumele.com"
                        },
                        timeout=SystemService.CHECK_TIMEOUT
                    )
                    latency = (datetime.utcnow() - start).total_seconds() * 1000
                    
                    if response.status_code == 200:
                        results["providers"]["openrouter"] = {
                            "status": "healthy",
                            "latency_ms": round(latency, 2),
                            "model": settings.OPENROUTER_MODEL,
                            "note": "Free tier available"
                        }
                        if results["status"] != "healthy":
                            results["status"] = "healthy"
                            results["active_provider"] = "openrouter"
                    else:
                        results["providers"]["openrouter"] = {
                            "status": "degraded",
                            "latency_ms": round(latency, 2),
                            "error": f"Status {response.status_code}"
                        }
            except Exception as e:
                results["providers"]["openrouter"] = {
                    "status": "unhealthy",
                    "error": str(e)[:100]
                }
        
        # Set final message
        healthy_providers = [k for k, v in results["providers"].items() if v.get("status") == "healthy"]
        if healthy_providers:
            results["status"] = "healthy"
            results["message"] = f"LLM available via: {', '.join(healthy_providers)}"
            if not results["active_provider"]:
                results["active_provider"] = healthy_providers[0]
        else:
            configured = list(results["providers"].keys())
            if configured:
                results["message"] = f"All configured providers unhealthy: {', '.join(configured)}"
            else:
                results["message"] = "No LLM providers configured (set OPENROUTER_API_KEY for free access)"
        
        return results

    @staticmethod
    async def check_translate() -> Dict[str, Any]:
        """Check translation service health."""
        start = datetime.utcnow()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.TRANSLATE_URL}/languages",
                    timeout=SystemService.CHECK_TIMEOUT
                )
                
                latency = (datetime.utcnow() - start).total_seconds() * 1000
                
                if response.status_code == 200:
                    return {
                        "status": "healthy",
                        "latency_ms": round(latency, 2),
                        "message": "Translation service healthy"
                    }
                else:
                    return {
                        "status": "degraded",
                        "latency_ms": round(latency, 2),
                        "message": f"Translation service returned {response.status_code}"
                    }
                    
        except Exception as e:
            return {
                "status": "unhealthy",
                "latency_ms": None,
                "message": str(e)
            }

    @staticmethod
    def get_system_metrics() -> Dict[str, Any]:
        """Get system resource metrics."""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "cpu": {
                    "percent": cpu_percent,
                    "status": "warning" if cpu_percent > SystemService.CPU_WARNING_THRESHOLD else "healthy"
                },
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "used_gb": round(memory.used / (1024**3), 2),
                    "percent": memory.percent,
                    "status": "warning" if memory.percent > SystemService.MEMORY_WARNING_THRESHOLD else "healthy"
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "used_gb": round(disk.used / (1024**3), 2),
                    "percent": round(disk.percent, 1),
                    "status": "warning" if disk.percent > SystemService.DISK_WARNING_THRESHOLD else "healthy"
                }
            }
            
        except Exception as e:
            logger.error(f"System metrics error: {e}")
            return {
                "cpu": {"status": "unknown"},
                "memory": {"status": "unknown"},
                "disk": {"status": "unknown"}
            }

    @staticmethod
    async def get_full_health(db: AsyncSession) -> Dict[str, Any]:
        """
        Get comprehensive AI system health status.
        Checks all components and returns unified health report.
        """
        start_time = datetime.utcnow()
        
        # Run all checks concurrently
        db_check, redis_check, qdrant_check, llm_check, translate_check = await asyncio.gather(
            SystemService.check_database(db),
            SystemService.check_redis(),
            SystemService.check_qdrant(),
            SystemService.check_llm(),
            SystemService.check_translate(),
            return_exceptions=True
        )
        
        # Handle any exceptions
        def safe_result(result, name):
            if isinstance(result, Exception):
                return {
                    "status": "error",
                    "message": str(result)
                }
            return result
        
        components = {
            "database": safe_result(db_check, "database"),
            "redis": safe_result(redis_check, "redis"),
            "qdrant": safe_result(qdrant_check, "qdrant"),
            "llm": safe_result(llm_check, "llm"),
            "translation": safe_result(translate_check, "translation")
        }
        
        # Get system metrics
        system_metrics = SystemService.get_system_metrics()
        
        # Calculate overall status
        statuses = [c.get("status", "unknown") for c in components.values()]
        
        if all(s == "healthy" for s in statuses):
            overall_status = "healthy"
        elif any(s == "unhealthy" for s in statuses):
            overall_status = "unhealthy"
        elif any(s == "degraded" for s in statuses):
            overall_status = "degraded"
        else:
            overall_status = "unknown"
        
        # Check system resources
        if system_metrics.get("cpu", {}).get("status") == "warning" or \
           system_metrics.get("memory", {}).get("status") == "warning":
            if overall_status == "healthy":
                overall_status = "degraded"
        
        total_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "check_duration_ms": round(total_time, 2),
            "components": components,
            "system": system_metrics,
            "version": {
                "api": "1.0.0",
                "python": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}"
            }
        }

    @staticmethod
    async def get_simple_health(db: AsyncSession) -> Dict[str, Any]:
        """Simple health check for load balancers."""
        try:
            # Just check database
            result = await db.execute(text("SELECT 1"))
            _ = result.scalar()
            
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }

    @staticmethod
    async def get_metrics() -> Dict[str, Any]:
        """Get Prometheus-style metrics."""
        metrics = SystemService.get_system_metrics()
        
        return {
            "kumele_cpu_usage_percent": metrics.get("cpu", {}).get("percent", 0),
            "kumele_memory_usage_percent": metrics.get("memory", {}).get("percent", 0),
            "kumele_memory_used_bytes": metrics.get("memory", {}).get("used_gb", 0) * (1024**3),
            "kumele_disk_usage_percent": metrics.get("disk", {}).get("percent", 0),
            "kumele_disk_used_bytes": metrics.get("disk", {}).get("used_gb", 0) * (1024**3)
        }
