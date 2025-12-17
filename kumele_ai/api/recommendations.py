"""
Recommendations Router - Personalized recommendation endpoints
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional
from sqlalchemy.orm import Session

from kumele_ai.dependencies import get_db
from kumele_ai.services.recommendation_service import recommendation_service

router = APIRouter()


@router.get("/events")
async def recommend_events(
    user_id: int = Query(..., description="User ID to get recommendations for"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    include_exploration: bool = Query(True, description="Include exploration items"),
    db: Session = Depends(get_db)
):
    """
    Get personalized event recommendations using TFRS hybrid approach.
    
    Returns events based on PREDICTED PREFERENCE using:
    - Content-based matching (hobby embeddings)
    - Collaborative filtering (similar users' behavior)
    - Light exploration (surface low-status high-relevance items)
    
    This is predicted preference, NOT objective relevance.
    Use /match/events for objective relevance.
    """
    results = recommendation_service.recommend_events(
        db=db,
        user_id=user_id,
        limit=limit,
        include_exploration=include_exploration
    )
    
    return {
        "user_id": user_id,
        "recommendation_type": "predicted_preference",
        "count": len(results),
        "events": results
    }


@router.get("/hobbies")
async def recommend_hobbies(
    user_id: int = Query(..., description="User ID to get recommendations for"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of results"),
    db: Session = Depends(get_db)
):
    """
    Suggest new hobbies/groups to user.
    
    Based on:
    - Events attended
    - Content read (blogs)
    - Engagement patterns
    - Similar users' hobbies
    """
    results = recommendation_service.recommend_hobbies(
        db=db,
        user_id=user_id,
        limit=limit
    )
    
    return {
        "user_id": user_id,
        "count": len(results),
        "hobbies": results
    }
