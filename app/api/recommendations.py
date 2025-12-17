"""
Recommendations API endpoints.
Handles personalized hobby and event recommendations.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import logging

from app.database import get_db
from app.services.recommendation_service import RecommendationService
from app.schemas.schemas import (
    HobbyRecommendationResponse,
    EventRecommendationResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get(
    "/hobbies",
    response_model=HobbyRecommendationResponse,
    summary="Get Hobby Recommendations",
    description="""
    Get personalized hobby recommendations for a user.
    
    Uses collaborative filtering and content-based recommendations:
    - Analyzes user's past interactions and preferences
    - Finds similar users and their hobby interests
    - Recommends new hobbies based on patterns
    
    Returns up to 10 hobby recommendations with confidence scores.
    """
)
async def get_hobby_recommendations(
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
    db: AsyncSession = Depends(get_db)
):
    """Get personalized hobby recommendations."""
    try:
        result = await RecommendationService.recommend_hobbies(
            db=db,
            user_id=user_id,
            limit=limit
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Hobby recommendations error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/events",
    response_model=EventRecommendationResponse,
    summary="Get Event Recommendations",
    description="""
    Get personalized event recommendations for a user.
    
    Recommendation factors:
    - User's hobby interests and past event attendance
    - Location preferences
    - Similar users' event choices
    - Event ratings and popularity
    - Time preferences
    
    Returns up to 10 event recommendations ranked by relevance.
    """
)
async def get_event_recommendations(
    user_id: str = Query(..., description="User ID"),
    location: Optional[str] = Query(None, description="Location filter"),
    category: Optional[str] = Query(None, description="Category filter"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
    db: AsyncSession = Depends(get_db)
):
    """Get personalized event recommendations."""
    try:
        result = await RecommendationService.recommend_events(
            db=db,
            user_id=user_id,
            location=location,
            category=category,
            limit=limit
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Event recommendations error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/refresh/{user_id}",
    summary="Refresh User Recommendations",
    description="Force refresh of cached recommendations for a user."
)
async def refresh_recommendations(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Refresh cached recommendations."""
    try:
        # Clear cache and regenerate
        hobbies = await RecommendationService.recommend_hobbies(db, user_id, limit=10)
        events = await RecommendationService.recommend_events(db, user_id, limit=10)
        
        # Cache new recommendations
        await RecommendationService.cache_recommendations(
            db=db,
            user_id=user_id,
            rec_type="hobby",
            recommendations=hobbies["recommendations"]
        )
        
        await RecommendationService.cache_recommendations(
            db=db,
            user_id=user_id,
            rec_type="event",
            recommendations=events["recommendations"]
        )
        
        await db.commit()
        
        return {
            "success": True,
            "message": "Recommendations refreshed",
            "hobby_count": len(hobbies["recommendations"]),
            "event_count": len(events["recommendations"])
        }
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Refresh recommendations error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/similar-users/{user_id}",
    summary="Get Similar Users",
    description="Find users with similar interests (for debugging/analysis)."
)
async def get_similar_users(
    user_id: str,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """Get similar users."""
    try:
        similar = await RecommendationService.get_similar_users(
            db, user_id, limit
        )
        
        return {
            "user_id": user_id,
            "similar_users": similar
        }
        
    except Exception as e:
        logger.error(f"Get similar users error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
