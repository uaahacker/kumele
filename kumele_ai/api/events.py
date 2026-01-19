"""
Events Router - Event rating and operations endpoints
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from kumele_ai.dependencies import get_db
from kumele_ai.services.event_service import event_service

router = APIRouter()


class EventRatingRequest(BaseModel):
    user_id: int
    rating: float  # 1-5
    communication_score: Optional[float] = None
    respect_score: Optional[float] = None
    professionalism_score: Optional[float] = None
    atmosphere_score: Optional[float] = None
    value_score: Optional[float] = None
    comment: Optional[str] = None


@router.post("/{event_id}/rating")
async def submit_event_rating(
    event_id: int,
    request: EventRatingRequest,
    db: Session = Depends(get_db)
):
    """
    Submit a rating for an event.
    
    Rules:
    - User must be an attendee and checked-in
    - One rating per event per user
    - Comment must pass moderation API
    - Rating and feedback are persisted
    """
    result = event_service.submit_rating(
        db=db,
        event_id=event_id,
        user_id=request.user_id,
        rating=request.rating,
        communication_score=request.communication_score,
        respect_score=request.respect_score,
        professionalism_score=request.professionalism_score,
        atmosphere_score=request.atmosphere_score,
        value_score=request.value_score,
        comment=request.comment
    )
    
    return result


@router.get("/{event_id}/ratings")
async def get_event_ratings(
    event_id: int,
    db: Session = Depends(get_db)
):
    """
    Get all ratings for an event.
    """
    result = event_service.get_event_ratings(
        db=db,
        event_id=event_id
    )
    
    return result
