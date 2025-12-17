"""
Pricing and Discount API endpoints.

Handles dynamic pricing optimization and discount suggestions.

Pricing Factors:
- Time: Price adjusts as event date approaches (early bird → last minute)
- Demand: Based on views, bookings, conversion rate
- Seasonality: Month and day-of-week adjustments
- Capacity: Current booking percentage

Price Bounds:
- Prices bounded to ±50% of base price
- Prevents extreme price swings

Discount Logic:
- Low booking (<30%) → Suggest promotional discount
- Last minute (<48h) → Special pricing
- High demand (>85%) → No discount needed

Storage:
- pricing_history: Tracks all calculations
- discount_suggestions: Recommended discounts
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime
import logging

from app.database import get_db
from app.services.pricing_service import PricingService
from app.schemas.schemas import (
    PriceOptimizeResponse,
    DiscountSuggestionResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pricing", tags=["Pricing"])


@router.get(
    "/optimise",
    response_model=PriceOptimizeResponse,
    summary="Optimize Event Price",
    description="""
    Get optimized price recommendation for an event.
    
    Factors considered:
    - **Time**: Price adjusts as event date approaches
    - **Demand**: Based on views, bookings, conversion rate
    - **Seasonality**: Month and day-of-week adjustments
    - **Capacity**: Current booking percentage
    
    Returns:
    - Suggested price
    - Price change percentage
    - Factor breakdown
    - Confidence score
    - Recommendation text
    
    Prices bounded to ±50% of base price.
    """
)
async def optimize_price(
    event_id: str = Query(..., description="Event ID"),
    base_price: float = Query(..., ge=0, description="Current base price"),
    event_date: datetime = Query(..., description="Event date"),
    category: Optional[str] = Query(None, description="Event category"),
    location: Optional[str] = Query(None, description="Event location"),
    db: AsyncSession = Depends(get_db)
):
    """Get optimized price for event."""
    try:
        result = await PricingService.optimize_price(
            db=db,
            event_id=event_id,
            base_price=base_price,
            event_date=event_date,
            category=category,
            location=location
        )
        
        await db.commit()
        return result
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Price optimization error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/history/{event_id}",
    summary="Get Pricing History",
    description="Get historical pricing calculations for an event."
)
async def get_pricing_history(
    event_id: str,
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db)
):
    """Get pricing history."""
    try:
        result = await PricingService.get_pricing_history(db, event_id, days)
        
        return {
            "event_id": event_id,
            "history": result
        }
        
    except Exception as e:
        logger.error(f"Get pricing history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Discount Router
discount_router = APIRouter(prefix="/discount", tags=["Discounts"])


@discount_router.get(
    "/suggestion",
    response_model=DiscountSuggestionResponse,
    summary="Get Discount Suggestions",
    description="""
    Get personalized discount suggestions.
    
    Discount types:
    - **new_user**: Welcome discount for new users (first 30 days)
    - **loyalty**: Reward for returning users
    - **low_demand**: Promotional discount for underbooked events
    - **last_minute**: Deal for events starting soon
    - **category_promo**: Category-specific promotions
    - **referral**: Referral program discounts
    
    Suggestions ranked by relevance score.
    Returns top 5 most relevant discounts.
    """
)
async def get_discount_suggestions(
    user_id: Optional[str] = Query(None, description="User ID for personalization"),
    event_id: Optional[str] = Query(None, description="Event ID for event-specific discounts"),
    category: Optional[str] = Query(None, description="Category for category discounts"),
    db: AsyncSession = Depends(get_db)
):
    """Get discount suggestions."""
    try:
        result = await PricingService.suggest_discount(
            db=db,
            user_id=user_id,
            event_id=event_id,
            category=category
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Discount suggestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@discount_router.post(
    "/validate",
    summary="Validate Discount Code",
    description="Validate a discount code and check eligibility."
)
async def validate_discount_code(
    code: str = Query(..., description="Discount code"),
    user_id: Optional[str] = Query(None, description="User ID"),
    event_id: Optional[str] = Query(None, description="Event ID"),
    db: AsyncSession = Depends(get_db)
):
    """Validate discount code."""
    try:
        # Simple validation - in production would check database
        valid_codes = {
            "WELCOME15": {"discount_percent": 15, "type": "new_user"},
            "LOYAL10": {"discount_percent": 10, "type": "loyalty"},
            "OUTDOOR20": {"discount_percent": 20, "type": "category_promo"},
            "LEARN15": {"discount_percent": 15, "type": "category_promo"},
            "SOCIAL10": {"discount_percent": 10, "type": "category_promo"},
            "KUMELE10": {"discount_percent": 10, "type": "general"},
            "REFER20": {"discount_percent": 20, "type": "referral"}
        }
        
        code_upper = code.upper()
        
        if code_upper in valid_codes:
            code_info = valid_codes[code_upper]
            return {
                "valid": True,
                "code": code_upper,
                "discount_percent": code_info["discount_percent"],
                "type": code_info["type"],
                "message": f"Code valid for {code_info['discount_percent']}% discount"
            }
        else:
            return {
                "valid": False,
                "code": code,
                "message": "Invalid or expired discount code"
            }
            
    except Exception as e:
        logger.error(f"Validate code error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@discount_router.get(
    "/active",
    summary="Get Active Promotions",
    description="Get all currently active promotions."
)
async def get_active_promotions(
    db: AsyncSession = Depends(get_db)
):
    """Get active promotions."""
    try:
        promotions = await PricingService._get_general_promotions(db)
        
        return {
            "promotions": promotions,
            "count": len(promotions)
        }
        
    except Exception as e:
        logger.error(f"Get promotions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
