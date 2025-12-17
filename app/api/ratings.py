"""
Rating API endpoints.

Handles weighted 5-star host rating model.

=============================================================================
HOST RATING SYSTEM (Section 3D of Requirements)
=============================================================================

Overview:
Weighted rating system combining attendee feedback with system metrics.

Rating Formula:
Final = (0.70 × Attendee Avg) + (0.30 × System Score)

Attendee Rating (70%):
- Direct 1-5 star ratings from verified attendees
- Only users who attended can rate
- Weighted by recency (newer = more weight)

System Score (30%):
- Response rate to inquiries
- Cancellation rate (lower = better)
- No-show rate (lower = better)
- Event completion rate
- Capacity utilization

Rating Display:
- 4.5+ : Excellent (gold badge)
- 4.0-4.5: Very Good (silver badge)
- 3.5-4.0: Good
- 3.0-3.5: Average
- <3.0: Below Average (review trigger)

Endpoints:
- POST /rating/event/{event_id}: Submit event rating
- GET /rating/host/{host_id}: Get host aggregate rating
- GET /rating/event/{event_id}/breakdown: Rating breakdown
- POST /rating/recalculate: Force aggregate recalc

Rules:
- One rating per user per event
- Can update within 7 days
- Cannot rate own events
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging

from app.database import get_db
from app.services.rating_service import RatingService
from app.schemas.schemas import (
    RatingSubmission,
    RatingResponse,
    HostRatingResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rating", tags=["Rating"])


@router.post(
    "/event/{event_id}",
    response_model=RatingResponse,
    summary="Submit Event Rating",
    description="""
    Submit a rating for an event. 
    
    Rules:
    - User must have attended the event
    - Event must have ended
    - User can only rate once per event
    
    The rating triggers recalculation of the host's weighted score:
    Host Score = (0.7 × Attendee Rating %) + (0.3 × System Reliability %)
    """
)
async def submit_event_rating(
    event_id: str,
    rating: RatingSubmission,
    db: AsyncSession = Depends(get_db)
):
    """Submit a rating for an event."""
    try:
        result = await RatingService.submit_rating(
            db=db,
            event_id=event_id,
            user_id=rating.user_id,
            rating=rating.rating,
            feedback=rating.feedback
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        await db.commit()
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Rating submission error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/host/{host_id}",
    response_model=HostRatingResponse,
    summary="Get Host Rating",
    description="""
    Get the aggregated rating for a host.
    
    Returns:
    - Weighted score (0-5 stars)
    - Attendee average rating
    - System reliability score
    - Event stats (total hosted, total attended)
    - Earned badges
    
    Formula: Host Score = (0.7 × Attendee Rating %) + (0.3 × System Reliability %)
    """
)
async def get_host_rating(
    host_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get aggregated host rating."""
    try:
        result = await RatingService.get_host_rating(db, host_id)
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get host rating error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/recalculate/{host_id}",
    summary="Recalculate Host Rating",
    description="Manually trigger recalculation of host's rating (admin use)."
)
async def recalculate_host_rating(
    host_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Manually recalculate host rating."""
    try:
        result = await RatingService.recalculate_host_rating(db, host_id)
        await db.commit()
        return result
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Recalculate rating error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/check/{event_id}/{user_id}",
    summary="Check Rating Eligibility",
    description="Check if a user can rate an event."
)
async def check_rating_eligibility(
    event_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Check if user can rate an event."""
    try:
        can_rate, reason = await RatingService.check_user_can_rate(
            db, event_id, user_id
        )
        
        return {
            "can_rate": can_rate,
            "reason": reason
        }
        
    except Exception as e:
        logger.error(f"Check eligibility error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
