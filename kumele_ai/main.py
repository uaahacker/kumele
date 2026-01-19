"""
Main FastAPI application for Kumele AI/ML Service
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from kumele_ai.config import settings
from kumele_ai.api import (
    chatbot,
    support,
    ml,
    translate,
    system,
    matching,
    recommendations,
    rewards,
    predictions,
    host,
    events,
    ads,
    nlp,
    moderation,
    pricing,
    discount,
    taxonomy,
    i18n
)
from kumele_ai.models.registry import model_registry

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.APP_DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Kumele AI/ML Service...")
    try:
        await model_registry.load_models()
        logger.info("Models loaded successfully")
    except Exception as e:
        logger.error(f"Error loading models: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Kumele AI/ML Service...")
    await model_registry.unload_models()


app = FastAPI(
    title="Kumele AI/ML Service",
    description="Backend AI/ML service for Kumele platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(system.router, tags=["System"])
app.include_router(chatbot.router, prefix="/chatbot", tags=["Chatbot"])
app.include_router(support.router, prefix="/support", tags=["Support"])
app.include_router(ml.router, prefix="/ml", tags=["ML"])
app.include_router(translate.router, prefix="/translate", tags=["Translation"])
app.include_router(matching.router, prefix="/match", tags=["Matching"])
app.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])
app.include_router(rewards.router, prefix="/rewards", tags=["Rewards"])
app.include_router(predictions.router, prefix="/predict", tags=["Predictions"])
app.include_router(host.router, prefix="/host", tags=["Host"])
app.include_router(events.router, prefix="/event", tags=["Events"])
app.include_router(ads.router, prefix="/ads", tags=["Ads"])
app.include_router(nlp.router, prefix="/nlp", tags=["NLP"])
app.include_router(moderation.router, prefix="/moderation", tags=["Moderation"])
app.include_router(pricing.router, prefix="/pricing", tags=["Pricing"])
app.include_router(discount.router, prefix="/discount", tags=["Discount"])
app.include_router(taxonomy.router, tags=["Taxonomy"])
app.include_router(i18n.router, tags=["i18n"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Kumele AI/ML",
        "version": "1.0.0",
        "status": "running"
    }
