"""
Advertising API endpoints.

Handles audience matching and ad performance prediction.

=============================================================================
ADS TARGETING SYSTEM (Section 3E of Requirements)
=============================================================================

Overview:
AI-powered advertising targeting that matches ads to relevant audience
segments based on demographics, interests, and behavior.

Capabilities:
- Audience segment matching based on user profiles
- CTR (Click-Through Rate) prediction
- Conversion prediction
- Budget optimization recommendations
- Performance analytics

Targeting Criteria:
- Demographics: age, gender, location
- Interests: hobby categories from taxonomy
- Behavior: event attendance, engagement level
- Lookalike: similar to high-value users

Endpoints:
- POST /ads/audience-match: Find matching audience for ad criteria
- POST /ads/predict-performance: Predict CTR and conversion rates
- GET /ads/segments: List available audience segments
- POST /ads/log: Log impressions and clicks

Integration:
- Uses same hobby taxonomy as recommendations
- Respects user privacy settings
- GDPR compliant (no PII in targeting)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import logging

from app.database import get_db
from app.services.ads_service import AdsService
from app.schemas.schemas import (
    AudienceMatchRequest,
    AudienceMatchResponse,
    AdPerformancePredictionRequest,
    AdPerformancePredictionResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ads", tags=["Advertising"])


@router.post(
    "/audience-match",
    response_model=AudienceMatchResponse,
    summary="Match Ad to Audience",
    description="""
    Match an ad to relevant audience segments.
    
    Analyzes:
    - Ad content and creative
    - Target demographics
    - Interest categories
    - Geographic targeting
    
    Returns matched audience segments with:
    - Segment size (reach)
    - Match score (0-100)
    - Segment demographics
    """
)
async def match_audience(
    request: AudienceMatchRequest,
    db: AsyncSession = Depends(get_db)
):
    """Match ad to audience segments."""
    try:
        result = await AdsService.find_audience_segments(
            db=db,
            ad_id=request.ad_id,
            ad_content=request.ad_content,
            target_interests=request.target_interests,
            target_locations=request.target_locations,
            target_age_min=request.target_age_min,
            target_age_max=request.target_age_max
        )
        
        await db.commit()
        return result
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Audience match error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/performance-predict",
    response_model=AdPerformancePredictionResponse,
    summary="Predict Ad Performance",
    description="""
    Predict performance metrics for an ad campaign.
    
    Uses:
    - Text sentiment/clarity analysis
    - Image embeddings (if available)
    - Historical campaign data
    
    Predicts:
    - Expected impressions
    - Estimated CTR (Click-Through Rate)
    - Estimated CPC (Cost Per Click)
    - Engagement rate
    - Conversion probability
    
    Persists predictions in ad_predictions table.
    """
)
async def predict_performance(
    request: AdPerformancePredictionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Predict ad campaign performance."""
    try:
        result = await AdsService.predict_performance(
            db=db,
            ad_id=request.ad_id,
            budget=request.budget,
            duration_days=request.duration_days,
            audience_segment_ids=request.audience_segment_ids,
            ad_content=request.ad_content
        )
        
        await db.commit()
        return result
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Performance prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/segments",
    summary="List Audience Segments",
    description="Get all available audience segments."
)
async def list_segments(
    category: Optional[str] = Query(None, description="Filter by category"),
    min_size: Optional[int] = Query(None, description="Minimum segment size"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """List audience segments."""
    try:
        result = await AdsService.list_segments(
            db=db,
            category=category,
            min_size=min_size,
            limit=limit,
            offset=offset
        )
        
        return result
        
    except Exception as e:
        logger.error(f"List segments error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/segment/{segment_id}",
    summary="Get Segment Details",
    description="Get detailed information about an audience segment."
)
async def get_segment(
    segment_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get segment details."""
    try:
        result = await AdsService.get_segment_details(db, segment_id)
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get segment error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/predictions/{ad_id}",
    summary="Get Historical Predictions",
    description="Get historical predictions for an ad."
)
async def get_predictions(
    ad_id: str,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """Get historical predictions."""
    try:
        result = await AdsService.get_predictions(db, ad_id, limit)
        return result
        
    except Exception as e:
        logger.error(f"Get predictions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
