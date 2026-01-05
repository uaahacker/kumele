"""
Recommendations API endpoints.

Handles personalized hobby and event recommendations.

=============================================================================
RECOMMENDATION ENGINE (Section 3A of Requirements)
=============================================================================

Overview:
Personalized recommendations using collaborative filtering + content-based
approaches. Supports cold start users via demographic fallback.

Algorithm:
1. Cold Start (<5 interactions):
   - Demographic-based (age, location, hobbies)
   - Popular events nearby
   - Diversity requirement (max 3 per category)

2. Warm Users (5+ interactions):
   - Collaborative: Similar users' preferences
   - Content-based: Hobby profile matching
   - Hybrid: 0.6 collab + 0.4 content

Score Boosting:
- Reward tier: none/bronze/silver/gold → 0/5/10/15%
- Engagement weight (RSVPs, attendance, etc.)
- Host rating factor
- Recency decay

Endpoints:
- GET /recommendations/hobbies: Recommend hobbies
- POST /recommendations/events: Recommend events
- POST /recommendations/train: Trigger model training
- GET /recommendations/cache: Cache status

Key Difference from /match/events:
- /match/events = Objective relevance (distance + hobby)
- /recommendations/events = Predicted preference (ML model)

Cache:
- Results cached 1 hour per user
- Invalidated on new interaction
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
            recommendations=hobbies.get("recommendations", [])
        )
        
        await RecommendationService.cache_recommendations(
            db=db,
            user_id=user_id,
            rec_type="event",
            recommendations=events.get("recommendations", [])
        )
        
        await db.commit()
        
        return {
            "success": True,
            "message": "Recommendations refreshed",
            "hobby_count": len(hobbies.get("recommendations", [])),
            "event_count": len(events.get("recommendations", []))
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


# =============================================================================
# TFRS TWO-TOWER MODEL ENDPOINTS
# =============================================================================

@router.get(
    "/tfrs/events",
    summary="TFRS Event Recommendations",
    description="""
    Get personalized event recommendations using TensorFlow Recommenders (TFRS) 
    Two-Tower architecture.
    
    Two-Tower Model:
    - **User Tower**: Encodes user features (hobbies, engagement, demographics, rewards)
    - **Event Tower**: Encodes event features (category, tags, host rating, engagement)
    - **Scoring**: Dot-product similarity for fast retrieval
    
    ML Inputs:
    - User hobbies and preference scores
    - Event attendance history
    - Blog/article reading patterns
    - Ad interaction behavior
    - Reward tier status
    - Location preferences
    
    Returns ranked events with explainable reasons.
    """
)
async def get_tfrs_recommendations(
    user_id: str = Query(..., description="User ID"),
    category: Optional[str] = Query(None, description="Category filter"),
    location: Optional[str] = Query(None, description="Location filter"),
    limit: int = Query(20, ge=1, le=50, description="Max results"),
    db: AsyncSession = Depends(get_db)
):
    """Get TFRS-based personalized recommendations."""
    try:
        # Import here to avoid circular imports
        from app.services.tfrs_service import TFRSService
        
        result = await TFRSService.get_recommendations(
            db=db,
            user_id=user_id,
            limit=limit,
            category_filter=category,
            location_filter=location
        )
        
        return result
        
    except Exception as e:
        logger.error(f"TFRS recommendations error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/tfrs/user-embedding/{user_id}",
    summary="Generate User Embedding",
    description="""
    Generate and store User Tower embedding for a user.
    
    Combines:
    - Hobby preferences (35%)
    - Engagement history (25%)
    - Demographics (15%)
    - Reward tier (10%)
    - Blog interests (10%)
    - Ad interactions (5%)
    
    Stores embedding in Qdrant for fast similarity search.
    """
)
async def generate_user_embedding(
    user_id: str,
    store_to_qdrant: bool = Query(True, description="Store embedding to Qdrant"),
    db: AsyncSession = Depends(get_db)
):
    """Generate and optionally store user embedding."""
    try:
        from app.services.tfrs_service import TFRSService
        
        embedding, features = await TFRSService.generate_user_embedding(db, user_id)
        
        if store_to_qdrant:
            stored = await TFRSService.store_user_embedding_to_qdrant(
                user_id, embedding, features
            )
        else:
            stored = False
        
        return {
            "user_id": user_id,
            "embedding_dimension": len(embedding),
            "features_extracted": list(features.keys()),
            "stored_to_qdrant": stored,
            "embedding_sample": embedding[:10]  # First 10 dims for debugging
        }
        
    except Exception as e:
        logger.error(f"Generate user embedding error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/tfrs/event-embedding/{event_id}",
    summary="Generate Event Embedding",
    description="""
    Generate and store Event Tower embedding for an event.
    
    Combines:
    - Category (30%)
    - Tags (25%)
    - Host rating (20%)
    - Engagement stats (15%)
    - Price tier (10%)
    
    Stores embedding in Qdrant for fast similarity search.
    """
)
async def generate_event_embedding(
    event_id: int,
    store_to_qdrant: bool = Query(True, description="Store embedding to Qdrant"),
    db: AsyncSession = Depends(get_db)
):
    """Generate and optionally store event embedding."""
    try:
        from app.services.tfrs_service import TFRSService
        from app.models.database_models import Event
        from sqlalchemy import select
        
        # Get event
        query = select(Event).where(Event.event_id == event_id)
        result = await db.execute(query)
        event = result.scalar_one_or_none()
        
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        
        embedding, features = await TFRSService.generate_event_embedding(db, event)
        
        if store_to_qdrant:
            stored = await TFRSService.store_event_embedding_to_qdrant(
                str(event_id), embedding, features
            )
        else:
            stored = False
        
        return {
            "event_id": event_id,
            "embedding_dimension": len(embedding),
            "features_extracted": features,
            "stored_to_qdrant": stored,
            "embedding_sample": embedding[:10]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate event embedding error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
