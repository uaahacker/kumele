"""
Rewards Router - User rewards and coupons endpoints
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from kumele_ai.dependencies import get_db
from kumele_ai.services.rewards_service import rewards_service

router = APIRouter()


@router.get("/suggestion")
async def get_reward_suggestion(
    user_id: int = Query(..., description="User ID to get rewards for"),
    db: Session = Depends(get_db)
):
    """
    Get reward suggestion for a user.
    
    Returns:
    - Current reward tier(s)
    - Progress toward next tier
    - Available unredeemed coupons
    - Reward history
    
    Reward Rules (evaluation window: last 30 days):
    - Only successful events count (attended & checked in, or hosted & completed)
    
    Tiers:
    - Bronze: >=1 event. Reward: none. Stackable: no. One-time.
    - Silver: >=3 events. Reward: 1×4% discount. Stackable: no. One-time.
    - Gold: >=4 events. Reward: 8% discount per Gold. Stackable: yes.
    
    Progression: Linear (Bronze → Silver → Gold)
    Gold count formula: floor(total_events_last_30_days / 4)
    """
    result = rewards_service.get_reward_suggestion(
        db=db,
        user_id=user_id
    )
    
    return result
