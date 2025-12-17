"""
Kumele AI/ML Backend API
Main FastAPI application entry point.
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
    
    ### Features
    
    #### 🌟 Rating System
    - Weighted 5-star host rating model
    - 70% attendee rating + 30% system reliability
    - Badge system for top performers
    
    #### 🎯 Recommendations
    - Personalized hobby recommendations
    - Event recommendations based on user preferences
    - Collaborative filtering + content-based hybrid
    
    #### 📢 Advertising Intelligence
    - Audience segment matching
    - Ad performance prediction
    - CTR and engagement forecasting
    
    #### 📝 NLP Services
    - Sentiment analysis
    - Keyword extraction
    - Trend detection
    
    #### 🛡️ Content Moderation
    - Text moderation (toxicity, hate, spam)
    - Image moderation (nudity, violence)
    - Video moderation with keyframe analysis
    
    #### 🤖 Chatbot
    - RAG-based knowledge Q&A
    - Multi-language support
    - Knowledge base sync
    
    #### 🌐 Translation & i18n
    - Real-time text translation
    - UI string management
    - 6 supported languages
    
    #### 📧 Support System
    - AI-powered email routing
    - Sentiment-based prioritization
    - Auto-generated reply drafts
    
    #### 💰 Dynamic Pricing
    - Price optimization
    - Discount suggestions
    - Time/demand-based pricing
    
    #### ❤️ System Health
    - Comprehensive health checks
    - Component monitoring
    - System metrics
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
            "detail": str(exc) if settings.DEBUG else "An unexpected error occurred"
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
        reload=settings.DEBUG
    )
