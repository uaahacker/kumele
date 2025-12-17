"""
Rewards Service for Rules-Based Gamification.
NOT ML - pure business logic with deterministic, auditable rules.
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from datetime import datetime, timedelta
import logging
import uuid
from decimal import Decimal

from app.models.database_models import (
    User, Event, EventAttendance, UserActivity, RewardCoupon, UserRewardProgress
)
from app.config import settings

logger = logging.getLogger(__name__)


class RewardsService:
    """
    Rules-based rewards/gamification service.
    
    Tier Rules (30-day window):
    - Bronze: ≥1 created or attended → No discount
    - Silver: ≥3 created or attended → 4% (one-time)
    - Gold: ≥4 created or attended → 8% per Gold (stackable)
    
    Gold stacking: gold_count = floor(total_successful_events / 4)
    """
    
    # Evaluation window in days
    EVALUATION_WINDOW_DAYS = 30
    
    # Tier thresholds
    TIER_THRESHOLDS = {
        "bronze": 1,
        "silver": 3,
        "gold": 4,
    }
    
    # Tier discounts
    TIER_DISCOUNTS = {
        "none": 0,
        "bronze": 0,
        "silver": 4,
        "gold": 8,
    }

    @staticmethod
    def calculate_tier(successful_events: int) -> Dict[str, Any]:
        """
        Calculate tier and gold count from successful events.
        Returns tier info with stacking details.
        """
        if successful_events < RewardsService.TIER_THRESHOLDS["bronze"]:
            return {
                "tier": "none",
                "gold_count": 0,
                "discount_percent": 0,
                "stackable": False
            }
        elif successful_events < RewardsService.TIER_THRESHOLDS["silver"]:
            return {
                "tier": "bronze",
                "gold_count": 0,
                "discount_percent": 0,
                "stackable": False
            }
        elif successful_events < RewardsService.TIER_THRESHOLDS["gold"]:
            return {
                "tier": "silver",
                "gold_count": 0,
                "discount_percent": 4,
                "stackable": False
            }
        else:
            # Gold tier with stacking
            gold_count = successful_events // RewardsService.TIER_THRESHOLDS["gold"]
            total_discount = gold_count * RewardsService.TIER_DISCOUNTS["gold"]
            return {
                "tier": "gold",
                "gold_count": gold_count,
                "discount_percent": total_discount,
                "stackable": True
            }

    @staticmethod
    def calculate_progress(successful_events: int) -> Dict[str, Any]:
        """Calculate progress to next tier."""
        if successful_events < RewardsService.TIER_THRESHOLDS["bronze"]:
            next_tier = "bronze"
            events_needed = RewardsService.TIER_THRESHOLDS["bronze"] - successful_events
            progress_percent = (successful_events / RewardsService.TIER_THRESHOLDS["bronze"]) * 100
        elif successful_events < RewardsService.TIER_THRESHOLDS["silver"]:
            next_tier = "silver"
            events_needed = RewardsService.TIER_THRESHOLDS["silver"] - successful_events
            progress_percent = (successful_events / RewardsService.TIER_THRESHOLDS["silver"]) * 100
        elif successful_events < RewardsService.TIER_THRESHOLDS["gold"]:
            next_tier = "gold"
            events_needed = RewardsService.TIER_THRESHOLDS["gold"] - successful_events
            progress_percent = (successful_events / RewardsService.TIER_THRESHOLDS["gold"]) * 100
        else:
            # Already gold, show progress to next gold stack
            current_in_cycle = successful_events % RewardsService.TIER_THRESHOLDS["gold"]
            next_tier = "gold+1"
            events_needed = RewardsService.TIER_THRESHOLDS["gold"] - current_in_cycle
            progress_percent = (current_in_cycle / RewardsService.TIER_THRESHOLDS["gold"]) * 100
        
        return {
            "next_tier": next_tier,
            "events_needed": events_needed,
            "progress_percent": round(progress_percent, 1)
        }

    @staticmethod
    async def count_successful_events(
        db: AsyncSession,
        user_id: int,
        window_days: int = 30
    ) -> Dict[str, int]:
        """
        Count successful events in the evaluation window.
        
        Successful = attended (checked-in) OR hosted & completed
        """
        cutoff_date = datetime.utcnow() - timedelta(days=window_days)
        
        # Count attended events (checked-in)
        attended_query = select(func.count(EventAttendance.id)).where(
            and_(
                EventAttendance.user_id == user_id,
                EventAttendance.checked_in == True,
                EventAttendance.checked_in_at >= cutoff_date
            )
        )
        attended_result = await db.execute(attended_query)
        attended_count = attended_result.scalar() or 0
        
        # Count hosted & completed events
        hosted_query = select(func.count(Event.event_id)).where(
            and_(
                Event.host_id == user_id,
                Event.status == "completed",
                Event.event_date >= cutoff_date
            )
        )
        hosted_result = await db.execute(hosted_query)
        hosted_count = hosted_result.scalar() or 0
        
        total = attended_count + hosted_count
        
        return {
            "attended": attended_count,
            "hosted": hosted_count,
            "total": total
        }

    @staticmethod
    async def get_reward_suggestion(
        db: AsyncSession,
        user_id: str,
        include_history: bool = False
    ) -> Dict[str, Any]:
        """
        Get reward suggestion for a user.
        Returns current status, progress, and available coupons.
        """
        try:
            user_id_int = int(user_id)
        except ValueError:
            # Handle UUID or other format
            user_id_int = hash(user_id) % 1000000
        
        # Count successful events
        event_counts = await RewardsService.count_successful_events(db, user_id_int)
        
        # Calculate tier
        tier_info = RewardsService.calculate_tier(event_counts["total"])
        
        # Calculate progress
        progress_info = RewardsService.calculate_progress(event_counts["total"])
        
        # Get available coupons (mock for now - would query RewardCoupon table)
        available_coupons = []
        if tier_info["discount_percent"] > 0:
            available_coupons.append({
                "coupon_id": f"reward-{user_id}-{tier_info['tier']}",
                "discount_percent": tier_info["discount_percent"],
                "tier": tier_info["tier"],
                "stackable": tier_info["stackable"],
                "is_redeemed": False,
                "issued_at": datetime.utcnow().isoformat()
            })
        
        response = {
            "user_id": user_id,
            "current_status": {
                "tier": tier_info["tier"],
                "gold_count": tier_info["gold_count"],
                "total_discount_percent": tier_info["discount_percent"],
                "successful_events_30d": event_counts["total"],
                "events_attended": event_counts["attended"],
                "events_hosted": event_counts["hosted"]
            },
            "progress": {
                "next_tier": progress_info["next_tier"],
                "events_needed": progress_info["events_needed"],
                "progress_percent": progress_info["progress_percent"],
                "evaluation_window_days": RewardsService.EVALUATION_WINDOW_DAYS
            },
            "available_coupons": available_coupons,
            "computed_at": datetime.utcnow().isoformat()
        }
        
        if include_history:
            response["history"] = await RewardsService.get_reward_history(db, user_id)
        
        return response

    @staticmethod
    async def get_reward_progress(
        db: AsyncSession,
        user_id: str
    ) -> Dict[str, Any]:
        """Get detailed reward progress."""
        try:
            user_id_int = int(user_id)
        except ValueError:
            user_id_int = hash(user_id) % 1000000
        
        event_counts = await RewardsService.count_successful_events(db, user_id_int)
        tier_info = RewardsService.calculate_tier(event_counts["total"])
        progress_info = RewardsService.calculate_progress(event_counts["total"])
        
        # Calculate days remaining in window
        days_remaining = RewardsService.EVALUATION_WINDOW_DAYS
        
        return {
            "user_id": user_id,
            "current_tier": tier_info["tier"],
            "gold_count": tier_info["gold_count"],
            "successful_events": event_counts["total"],
            "events_breakdown": {
                "attended": event_counts["attended"],
                "hosted": event_counts["hosted"]
            },
            "next_tier": progress_info["next_tier"],
            "events_to_next_tier": progress_info["events_needed"],
            "progress_percent": progress_info["progress_percent"],
            "days_remaining_in_window": days_remaining,
            "window_end_date": (datetime.utcnow() + timedelta(days=days_remaining)).isoformat()
        }

    @staticmethod
    async def get_reward_history(
        db: AsyncSession,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """Get user's reward history."""
        # Mock history - in production would query RewardCoupon table
        return [
            {
                "coupon_id": "hist-001",
                "tier": "silver",
                "discount_percent": 4,
                "issued_at": (datetime.utcnow() - timedelta(days=45)).isoformat(),
                "redeemed_at": (datetime.utcnow() - timedelta(days=40)).isoformat(),
                "event_id": "event-123"
            }
        ]

    @staticmethod
    async def redeem_coupon(
        db: AsyncSession,
        coupon_id: str,
        user_id: str,
        event_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Redeem a coupon."""
        # In production, would update RewardCoupon table
        return {
            "success": True,
            "message": "Coupon redeemed successfully",
            "coupon_id": coupon_id,
            "event_id": event_id,
            "redeemed_at": datetime.utcnow().isoformat()
        }

    @staticmethod
    async def get_user_coupons(
        db: AsyncSession,
        user_id: str,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get user's coupons."""
        # Mock response - in production would query RewardCoupon table
        coupons = [
            {
                "coupon_id": f"coupon-{user_id}-001",
                "tier": "silver",
                "discount_percent": 4,
                "status": "active",
                "issued_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat()
            }
        ]
        
        if status:
            coupons = [c for c in coupons if c["status"] == status]
        
        return {
            "user_id": user_id,
            "coupons": coupons,
            "total_count": len(coupons)
        }

    @staticmethod
    async def compute_daily_rewards(db: AsyncSession) -> Dict[str, Any]:
        """
        Compute daily rewards for all active users.
        Called by cron job to issue new coupons.
        """
        # In production, would:
        # 1. Get all users with activity in last 30 days
        # 2. Calculate tier for each
        # 3. Issue new coupons where applicable
        # 4. Expire old coupons
        
        return {
            "success": True,
            "message": "Daily rewards computed",
            "computed_at": datetime.utcnow().isoformat(),
            "users_processed": 0,  # Would be actual count
            "coupons_issued": 0
        }
