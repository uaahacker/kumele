"""
Rewards Service - Handles reward calculations and coupon management
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from kumele_ai.db.models import (
    User, UserActivity, RewardCoupon, Event, UserEvent
)

logger = logging.getLogger(__name__)


class RewardsService:
    """Service for managing user rewards and coupons"""
    
    # Reward tier thresholds
    BRONZE_THRESHOLD = 1
    SILVER_THRESHOLD = 3
    GOLD_THRESHOLD = 4
    
    # Discount values
    BRONZE_DISCOUNT = 0  # No discount
    SILVER_DISCOUNT = 4  # 4%
    GOLD_DISCOUNT = 8    # 8%
    
    def get_user_activities_last_30_days(
        self,
        db: Session,
        user_id: int
    ) -> List[UserActivity]:
        """Get user activities from the last 30 days"""
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        activities = db.query(UserActivity).filter(
            and_(
                UserActivity.user_id == user_id,
                UserActivity.activity_date >= cutoff_date
            )
        ).all()
        
        return activities
    
    def count_successful_events(
        self,
        db: Session,
        user_id: int
    ) -> Dict[str, int]:
        """Count successful events (attended + hosted) in last 30 days"""
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        # Count events attended (checked in)
        attended_count = db.query(func.count(UserEvent.id)).join(Event).filter(
            and_(
                UserEvent.user_id == user_id,
                UserEvent.checked_in == True,
                Event.status == "completed",
                Event.event_date >= cutoff_date
            )
        ).scalar() or 0
        
        # Count events created and completed
        created_count = db.query(func.count(Event.id)).filter(
            and_(
                Event.host_id == user_id,
                Event.status == "completed",
                Event.event_date >= cutoff_date
            )
        ).scalar() or 0
        
        return {
            "attended": attended_count,
            "created": created_count,
            "total": attended_count + created_count
        }
    
    def calculate_tier(self, total_events: int) -> str:
        """Calculate reward tier based on total events"""
        if total_events >= self.GOLD_THRESHOLD:
            return "Gold"
        elif total_events >= self.SILVER_THRESHOLD:
            return "Silver"
        elif total_events >= self.BRONZE_THRESHOLD:
            return "Bronze"
        return "None"
    
    def calculate_gold_count(self, total_events: int) -> int:
        """Calculate how many Gold rewards user qualifies for"""
        return total_events // self.GOLD_THRESHOLD
    
    def get_progress_to_next_tier(
        self,
        current_tier: str,
        total_events: int
    ) -> Dict[str, Any]:
        """Calculate progress to next tier"""
        if current_tier == "None":
            return {
                "next_tier": "Bronze",
                "events_needed": self.BRONZE_THRESHOLD - total_events,
                "progress_percent": (total_events / self.BRONZE_THRESHOLD) * 100
            }
        elif current_tier == "Bronze":
            return {
                "next_tier": "Silver",
                "events_needed": self.SILVER_THRESHOLD - total_events,
                "progress_percent": (total_events / self.SILVER_THRESHOLD) * 100
            }
        elif current_tier == "Silver":
            return {
                "next_tier": "Gold",
                "events_needed": self.GOLD_THRESHOLD - total_events,
                "progress_percent": (total_events / self.GOLD_THRESHOLD) * 100
            }
        else:  # Gold
            next_gold = ((total_events // self.GOLD_THRESHOLD) + 1) * self.GOLD_THRESHOLD
            return {
                "next_tier": "Gold (additional)",
                "events_needed": next_gold - total_events,
                "progress_percent": ((total_events % self.GOLD_THRESHOLD) / self.GOLD_THRESHOLD) * 100
            }
    
    def get_user_coupons(
        self,
        db: Session,
        user_id: int,
        include_redeemed: bool = False
    ) -> List[RewardCoupon]:
        """Get user's reward coupons"""
        query = db.query(RewardCoupon).filter(
            RewardCoupon.user_id == user_id
        )
        
        if not include_redeemed:
            query = query.filter(RewardCoupon.is_redeemed == False)
        
        return query.all()
    
    def issue_coupon(
        self,
        db: Session,
        user_id: int,
        tier: str
    ) -> Optional[RewardCoupon]:
        """Issue a reward coupon for a tier"""
        # Determine discount value and stackability
        if tier == "Bronze":
            discount = self.BRONZE_DISCOUNT
            stackable = False
        elif tier == "Silver":
            # Check if user already has a Silver coupon
            existing_silver = db.query(RewardCoupon).filter(
                and_(
                    RewardCoupon.user_id == user_id,
                    RewardCoupon.status_level == "Silver"
                )
            ).first()
            
            if existing_silver:
                logger.info(f"User {user_id} already has Silver coupon")
                return None
            
            discount = self.SILVER_DISCOUNT
            stackable = False
        elif tier == "Gold":
            discount = self.GOLD_DISCOUNT
            stackable = True
        else:
            return None
        
        # Create coupon
        coupon = RewardCoupon(
            user_id=user_id,
            status_level=tier,
            discount_value=discount,
            stackable=stackable,
            is_redeemed=False
        )
        
        db.add(coupon)
        db.commit()
        db.refresh(coupon)
        
        logger.info(f"Issued {tier} coupon to user {user_id}")
        return coupon
    
    def get_reward_suggestion(
        self,
        db: Session,
        user_id: int
    ) -> Dict[str, Any]:
        """Get comprehensive reward suggestion for a user"""
        # Count successful events
        event_counts = self.count_successful_events(db, user_id)
        total_events = event_counts["total"]
        
        # Calculate current tier
        current_tier = self.calculate_tier(total_events)
        
        # Calculate gold count
        gold_count = self.calculate_gold_count(total_events)
        
        # Get progress to next tier
        progress = self.get_progress_to_next_tier(current_tier, total_events)
        
        # Get unredeemed coupons
        coupons = self.get_user_coupons(db, user_id, include_redeemed=False)
        unredeemed_coupons = [
            {
                "coupon_id": c.coupon_id,
                "tier": c.status_level,
                "discount_value": c.discount_value,
                "stackable": c.stackable,
                "issued_at": c.issued_at.isoformat() if c.issued_at else None
            }
            for c in coupons
        ]
        
        # Get reward history
        all_coupons = self.get_user_coupons(db, user_id, include_redeemed=True)
        reward_history = [
            {
                "coupon_id": c.coupon_id,
                "tier": c.status_level,
                "discount_value": c.discount_value,
                "is_redeemed": c.is_redeemed,
                "issued_at": c.issued_at.isoformat() if c.issued_at else None,
                "redeemed_at": c.redeemed_at.isoformat() if c.redeemed_at else None
            }
            for c in all_coupons
        ]
        
        # Calculate total stackable discount
        total_stackable_discount = sum(
            c.discount_value for c in coupons 
            if c.stackable and not c.is_redeemed
        )
        
        return {
            "user_id": user_id,
            "current_tier": current_tier,
            "gold_count": gold_count,
            "event_counts": event_counts,
            "progress": {
                "next_tier": progress["next_tier"],
                "events_needed": max(0, progress["events_needed"]),
                "progress_percent": min(100, progress["progress_percent"])
            },
            "unredeemed_coupons": unredeemed_coupons,
            "total_stackable_discount": total_stackable_discount,
            "reward_history": reward_history,
            "evaluation_window": "last_30_days"
        }
    
    def record_activity(
        self,
        db: Session,
        user_id: int,
        activity_type: str,
        event_id: int
    ) -> UserActivity:
        """Record a user activity for rewards tracking"""
        activity = UserActivity(
            user_id=user_id,
            activity_type=activity_type,
            event_id=event_id,
            activity_date=datetime.utcnow()
        )
        
        db.add(activity)
        db.commit()
        db.refresh(activity)
        
        # Check if user qualifies for new rewards
        self._check_and_issue_rewards(db, user_id)
        
        return activity
    
    def _check_and_issue_rewards(self, db: Session, user_id: int):
        """Check if user qualifies for any new rewards and issue them"""
        event_counts = self.count_successful_events(db, user_id)
        total_events = event_counts["total"]
        
        # Check for Bronze
        if total_events >= self.BRONZE_THRESHOLD:
            existing = db.query(RewardCoupon).filter(
                and_(
                    RewardCoupon.user_id == user_id,
                    RewardCoupon.status_level == "Bronze"
                )
            ).first()
            if not existing:
                self.issue_coupon(db, user_id, "Bronze")
        
        # Check for Silver
        if total_events >= self.SILVER_THRESHOLD:
            self.issue_coupon(db, user_id, "Silver")  # Will check for existing
        
        # Check for Gold (can have multiple)
        gold_count = self.calculate_gold_count(total_events)
        existing_gold = db.query(func.count(RewardCoupon.coupon_id)).filter(
            and_(
                RewardCoupon.user_id == user_id,
                RewardCoupon.status_level == "Gold"
            )
        ).scalar() or 0
        
        # Issue additional Gold coupons if qualified
        while existing_gold < gold_count:
            self.issue_coupon(db, user_id, "Gold")
            existing_gold += 1


# Singleton instance
rewards_service = RewardsService()
