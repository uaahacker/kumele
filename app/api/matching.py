"""
Matching API endpoints.
Handles event matching based on location, hobbies, and engagement.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import logging

from app.database import get_db
from app.services.matching_service import MatchingService
from app.schemas.schemas import (
    EventMatchResponse,
    EventMatchItem
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/match", tags=["Matching"])


@router.get(
    "/events",
    response_model=EventMatchResponse,
    summary="Match Events",
    description="""
    Get events matched to user based on multiple factors.
    
    **Matching Pipeline:**
    1. Convert address → lat/lon (OpenStreetMap Nominatim)
    2. Compute distance (Haversine formula)
    3. Create hobby/event embeddings (Hugging Face)
    4. Compute hybrid relevance score (collab + content)
    5. Final re-ranking score combining:
       - Distance score (closer = higher)
       - Hobby similarity score
       - Engagement weight
       - Reward/trust boosting
    
    **Required Inputs:**
    - User profile: hobbies, age, location (lat/lon)
    - Event profile: hobby tags, location, time
    - Engagement: RSVPs, attendance, blogs read, ads clicked
    - Reward status: none/bronze/silver/gold
    - User reputation (complaints vs real attendance)
    
    **Output includes score breakdown for debugging/UI transparency.**
    
    Works for new users with fallback logic (popular events nearby).
    """
)
async def match_events(
    user_id: str = Query(..., description="User ID"),
    lat: Optional[float] = Query(None, description="User latitude"),
    lon: Optional[float] = Query(None, description="User longitude"),
    address: Optional[str] = Query(None, description="Address for geocoding"),
    max_distance_km: float = Query(50.0, ge=1, le=500, description="Max distance in km"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    db: AsyncSession = Depends(get_db)
):
    """Get matched events for user."""
    try:
        result = await MatchingService.match_events(
            db=db,
            user_id=user_id,
            lat=lat,
            lon=lon,
            address=address,
            max_distance_km=max_distance_km,
            category=category,
            limit=limit
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Event matching error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/score-breakdown/{event_id}",
    summary="Get Match Score Breakdown",
    description="Get detailed score breakdown for a specific event match."
)
async def get_score_breakdown(
    event_id: str,
    user_id: str = Query(..., description="User ID"),
    db: AsyncSession = Depends(get_db)
):
    """Get score breakdown for an event match."""
    try:
        result = await MatchingService.get_score_breakdown(
            db=db,
            event_id=event_id,
            user_id=user_id
        )
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Score breakdown error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/geocode",
    summary="Geocode Address",
    description="Convert address to latitude/longitude using OpenStreetMap Nominatim."
)
async def geocode_address(
    address: str = Query(..., description="Address to geocode")
):
    """Geocode an address to lat/lon."""
    try:
        result = await MatchingService.geocode_address(address)
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("message"))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Geocode error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
