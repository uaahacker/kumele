"""
Kumele AI/ML Backend API - Main FastAPI Application Entry Point.

=============================================================================
KUMELE AI/ML BACKEND
=============================================================================

Production Server: http://104.248.178.34:8000

Tech Stack:
-----------
- FastAPI 0.109.0: Async REST API framework
- PostgreSQL: Primary database (async SQLAlchemy)
- Redis: Caching and Celery queue
- Qdrant: Vector database for RAG chatbot
- HuggingFace: ML models (sentiment, embeddings, moderation)
- LLM Chain: Internal TGI → Mistral API → OpenRouter (free fallback)

API Sections (per 8-section requirements):
------------------------------------------
1. Matching & Recommendations (/match, /recommendations)
2. Rewards System (/rewards) - rules-based
3. Predictions (/predictions) - Prophet + sklearn
4. Host Ratings (/rating) - 70% attendee + 30% system
5. Ads Targeting (/ads) - demographics + behavioral
6. NLP Processing (/nlp) - sentiment, keywords, trends
7. Content Moderation (/moderation) - text + image
8. Chatbot RAG (/chatbot) - multi-language Q&A
9. Translation/i18n (/translate, /i18n) - lazy loading
10. Support (/support) - email only, no live chat
11. Dynamic Pricing (/pricing, /discount)
12. Taxonomy (/taxonomy) - hobby categories
13. AI Health (/ai/health) - system monitoring

Environment Variables:
----------------------
- DATABASE_URL: PostgreSQL connection string
- REDIS_URL: Redis connection string
- QDRANT_URL: Qdrant vector DB URL
- LLM_API_URL: Internal TGI endpoint (optional)
- MISTRAL_API_KEY: Mistral API key (optional)
- OPENROUTER_API_KEY: OpenRouter API key (optional, free)
- HUGGINGFACE_API_KEY: HuggingFace model access

Documentation:
--------------
- Swagger UI: /docs
- ReDoc: /redoc
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import time

from app.config import settings
from app.database import init_db, close_db

# Import routers
from app.api.ratings import router as ratings_router
from app.api.recommendations import router as recommendations_router
from app.api.ads import router as ads_router
from app.api.nlp import router as nlp_router
from app.api.moderation import router as moderation_router
from app.api.chatbot import router as chatbot_router
from app.api.translate import router as translate_router, i18n_router, admin_i18n_router
from app.api.support import router as support_router
from app.api.pricing import router as pricing_router, discount_router
from app.api.system import router as system_router
from app.api.taxonomy import router as taxonomy_router
from app.api.rewards import router as rewards_router
from app.api.matching import router as matching_router
from app.api.predictions import router as predictions_router
from app.api.testing import router as testing_router
from app.api.feedback import router as feedback_router
from app.api.engagement import router as engagement_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    logger.info("Starting Kumele AI/ML Backend...")
    await init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Kumele AI/ML Backend...")
    await close_db()
    logger.info("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title="Kumele AI/ML Backend",
    description="""
    ## Comprehensive AI/ML Backend for Kumele Platform
    
    **Production URL**: http://104.248.178.34:8000
    
    ### Architecture Overview
    
    - **Database**: PostgreSQL (async via SQLAlchemy)
    - **Cache/Queue**: Redis (async)
    - **Vector DB**: Qdrant (chatbot RAG)
    - **ML Models**: HuggingFace Transformers
    - **LLM Fallback Chain**: Internal TGI → Mistral API → OpenRouter (free)
    
    ### API Sections (per Requirements Spec)
    
    #### 3A. 🎯 Matching & Recommendations
    - `/match/events` - Location + hobby similarity matching
    - `/recommendations/events` - ML-based personalized recommendations
    - `/recommendations/hobbies` - Hobby suggestions
    - Supports cold start users, engagement weighting, reward tier boosting
    
    #### 3B. 🎁 Rewards System
    - `/rewards/calculate` - Rules-based reward calculation
    - `/rewards/points` - Check user points
    - Tiers: none/bronze/silver/gold with boost percentages
    
    #### 3C. 📈 Predictions
    - `/predictions/event` - Prophet + sklearn event predictions
    - `/predictions/attendance` - Attendance forecasting
    - `/predictions/revenue` - Revenue optimization
    
    #### 3D. ⭐ Host Ratings
    - `/rating/event/{id}` - Submit rating (verified attendees only)
    - `/rating/host/{id}` - Get host aggregate (70% attendee + 30% system)
    - Badge system for top performers
    
    #### 3E. 📢 Ads Targeting
    - `/ads/audience-match` - Find matching audience segments
    - `/ads/predict-performance` - CTR/conversion prediction
    - Demographics + interests + behavioral targeting
    
    #### 3F. 📝 NLP Processing
    - `/nlp/sentiment` - Sentiment analysis (-1.0 to +1.0)
    - `/nlp/keywords` - TF-IDF + NER extraction
    - `/nlp/trends` - Trending topic detection
    
    #### 3G. 🛡️ Content Moderation
    - `/moderation` - Text/image moderation
    - `/moderation/job/{id}` - Async job status
    - Scoring: 0-0.3 safe, 0.3-0.7 review, 0.7-1.0 reject
    
    #### 3H. 🤖 Chatbot RAG
    - `/chatbot/ask` - RAG-powered Q&A (multi-language)
    - `/chatbot/sync` - Knowledge base sync
    - Pipeline: Translate → Embed → Qdrant → LLM → Translate back
    
    #### 3I. 🌐 Translation & i18n
    - `/i18n/strings` - Lazy-loaded UI translations
    - `/translate` - Dynamic content translation
    - Languages: en, ar (RTL), fr, es, de, tr, he (RTL)
    
    #### 3J. ❤️ AI Health
    - `/ai/health` - Full system health check
    - Components: DB, Redis, Qdrant, LLM (3 providers), ML models
    
    #### Additional
    - `/taxonomy` - Hobby/interest taxonomy (source of truth)
    - `/support` - Email-only support (no live chat)
    - `/pricing` - Dynamic pricing optimization
    
    ### Authentication
    All endpoints require valid JWT token in Authorization header.
    Testing endpoints available at `/testing/*` for development.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add request processing time to response headers."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.APP_DEBUG else "An unexpected error occurred"
        }
    )


# Include routers
app.include_router(ratings_router)
app.include_router(recommendations_router)
app.include_router(ads_router)
app.include_router(nlp_router)
app.include_router(moderation_router)
app.include_router(chatbot_router)
app.include_router(translate_router)
app.include_router(i18n_router)
app.include_router(admin_i18n_router)
app.include_router(support_router)
app.include_router(pricing_router)
app.include_router(discount_router)
app.include_router(system_router)
app.include_router(taxonomy_router)
app.include_router(rewards_router)
app.include_router(matching_router)
app.include_router(predictions_router)
app.include_router(testing_router)
app.include_router(feedback_router)
app.include_router(engagement_router)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Kumele AI/ML Backend",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/ai/health"
    }


# Ready endpoint for k8s probes
@app.get("/ready", tags=["Health"])
async def ready():
    """Readiness probe endpoint."""
    return {"status": "ready"}


# Live endpoint for k8s probes
@app.get("/live", tags=["Health"])
async def live():
    """Liveness probe endpoint."""
    return {"status": "alive"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.APP_DEBUG
    )
