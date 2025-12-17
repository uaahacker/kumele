"""
Pricing Router - Dynamic pricing optimization endpoints
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional
from sqlalchemy.orm import Session

from kumele_ai.dependencies import get_db
from kumele_ai.services.pricing_service import pricing_service

router = APIRouter()


@router.get("/optimise")
async def optimize_pricing(
    event_id: Optional[int] = Query(None, description="Event ID (optional)"),
    category: Optional[str] = Query(None, description="Event category"),
    city: Optional[str] = Query(None, description="City"),
    capacity: int = Query(50, description="Event capacity"),
    host_score: float = Query(50.0, description="Host score (0-100)"),
    day_of_week: Optional[int] = Query(None, description="Day of week (0=Mon, 6=Sun)"),
    db: Session = Depends(get_db)
):
    """
    Suggest optimal ticket price tiers based on historical demand.
    
    Logic:
    1. Retrieve similar past events (category, city, capacity, day/time)
    2. Regression model estimates: attendance = f(price, host_score, time_to_event, popularity, demand)
    3. Evaluate candidate prices, compute: revenue = price × expected_attendance
    4. Return top 3 tiers
    
    Returns:
    - recommended_tiers: Top 3 price tiers with expected attendance and revenue
    - optimal_price: Best single price recommendation
    - historical_metrics: Averages and elasticity from historical data
    """
    result = pricing_service.optimize_pricing(
        db=db,
        event_id=event_id,
        category=category,
        city=city,
        capacity=capacity,
        host_score=host_score,
        day_of_week=day_of_week
    )
    
    return result
