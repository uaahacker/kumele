"""
Rewards & Gamification API endpoints.
Rules-based reward system (NOT ML) - Bronze/Silver/Gold tiers.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging

from app.database import get_db
from app.services.rewards_service import RewardsService
from app.schemas.schemas import (
    RewardsSuggestionResponse,
    RewardProgressResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rewards", tags=["Rewards & Gamification"])


@router.get(
    "/suggestion",
    response_model=RewardsSuggestionResponse,
    summary="Get Reward Suggestion",
    description="""
    Get rewards/coupons suggestion for a user based on activity.
    
    **IMPORTANT: This is rules-based, NOT ML.**
    
    Evaluation window: **last 30 days only**
    
    Counts only successful events:
    - attended (not RSVP/no-show)
    - hosted & completed
    
    Tier Rules:
    | Tier   | Requirement (last 30 days) | Reward            | Stackable |
    |--------|----------------------------|-------------------|-----------|
    | Bronze | ≥1 created or attended     | No discount       | No        |
    | Silver | ≥3 created or attended     | 4% (one-time)     | No        |
    | Gold   | ≥4 created or attended     | 8% per Gold       | Yes       |
    
    Gold stacking formula:
    `gold_count = floor(total_successful_events_last_30_days / 4)`
    
    Returns:
    - current_status with Gold count
    - progress to next tier
    - available unredeemed coupons
    - history (optional)
    """
)
async def get_reward_suggestion(
    user_id: str = Query(..., description="User ID"),
    include_history: bool = Query(False, description="Include reward history"),
    db: AsyncSession = Depends(get_db)
):
    """Get reward suggestions for a user."""
    try:
        result = await RewardsService.get_reward_suggestion(
            db=db,
            user_id=user_id,
            include_history=include_history
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Reward suggestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/progress/{user_id}",
    response_model=RewardProgressResponse,
    summary="Get User Reward Progress",
    description="""
    Get detailed reward progress for a user.
    
    Shows:
    - Current tier status
    - Events counted in current window
    - Progress to next tier
    - Days remaining in evaluation period
    """
)
async def get_reward_progress(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get reward progress for a user."""
    try:
        result = await RewardsService.get_reward_progress(db, user_id)
        return result
        
    except Exception as e:
        logger.error(f"Reward progress error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/redeem/{coupon_id}",
    summary="Redeem Coupon",
    description="Redeem an available coupon."
)
async def redeem_coupon(
    coupon_id: str,
    user_id: str = Query(..., description="User ID"),
    event_id: Optional[str] = Query(None, description="Event ID to apply coupon"),
    db: AsyncSession = Depends(get_db)
):
    """Redeem a coupon."""
    try:
        result = await RewardsService.redeem_coupon(
            db=db,
            coupon_id=coupon_id,
            user_id=user_id,
            event_id=event_id
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("message"))
        
        await db.commit()
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Redeem coupon error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/coupons/{user_id}",
    summary="Get User Coupons",
    description="Get all coupons for a user (active and redeemed)."
)
async def get_user_coupons(
    user_id: str,
    status: Optional[str] = Query(None, description="Filter: active, redeemed, expired"),
    db: AsyncSession = Depends(get_db)
):
    """Get user's coupons."""
    try:
        result = await RewardsService.get_user_coupons(db, user_id, status)
        return result
        
    except Exception as e:
        logger.error(f"Get coupons error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/compute-daily",
    summary="Compute Daily Rewards (Admin/Cron)",
    description="Trigger daily reward computation for all users."
)
async def compute_daily_rewards(
    db: AsyncSession = Depends(get_db)
):
    """Compute daily rewards - called by cron job."""
    try:
        result = await RewardsService.compute_daily_rewards(db)
        await db.commit()
        return result
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Compute daily rewards error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
