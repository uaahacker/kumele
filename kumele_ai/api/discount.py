"""
Discount Router - Discount suggestion endpoints
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from kumele_ai.dependencies import get_db
from kumele_ai.services.pricing_service import pricing_service

router = APIRouter()


@router.get("/suggestion")
async def suggest_discounts(
    event_id: int = Query(..., description="Event ID"),
    base_price: float = Query(..., description="Base ticket price"),
    capacity: int = Query(50, description="Event capacity"),
    current_bookings: int = Query(0, description="Current number of bookings"),
    db: Session = Depends(get_db)
):
    """
    Recommend discount strategies for audience segments.
    
    Segments evaluated:
    - Gold/Silver/Bronze members
    - New users
    - Nearby users
    - Past attendees
    
    Logic:
    1. Prophet + regression estimate uplift for 5%, 8%, 10%, 15%, 20% discounts
    2. ROI = (uplift × expected_bookings) - discount_cost
    3. Return best ROI strategy per segment
    
    Returns:
    - suggestions: List of discount recommendations per segment
    - best_strategy: Highest ROI option
    """
    result = pricing_service.suggest_discounts(
        db=db,
        event_id=event_id,
        base_price=base_price,
        capacity=capacity,
        current_bookings=current_bookings
    )
    
    return result
