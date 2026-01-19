"""
Matching Router - Event matching endpoints
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional, List
from sqlalchemy.orm import Session

from kumele_ai.dependencies import get_db
from kumele_ai.services.matching_service import matching_service

router = APIRouter()


@router.get("/events")
async def match_events(
    user_id: int = Query(..., description="User ID to match events for"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    hobby: Optional[str] = Query(None, description="Filter by hobby name"),
    location: Optional[str] = Query(None, description="Filter by location/city"),
    db: Session = Depends(get_db)
):
    """
    Return nearest relevant events ranked by OBJECTIVE RELEVANCE score.
    
    This endpoint returns events based on:
    - Distance score (30%)
    - Hobby similarity via embeddings (50%)
    - Engagement weight from past interactions (20%)
    
    This is objective relevance, NOT predicted preference.
    Use /recommendations/events for personalized preferences.
    """
    results = matching_service.match_events(
        db=db,
        user_id=user_id,
        limit=limit,
        hobby_filter=hobby,
        location_filter=location
    )
    
    return {
        "user_id": user_id,
        "match_type": "objective_relevance",
        "count": len(results),
        "events": results
    }
