"""
NFT Badge Intelligence Service

Manages NFT badges for trust and reputation:
- Badge issuance based on verified attendance
- Trust score calculations
- Matching priority for badge holders
- Price discounts based on badge level

Badge Tiers:
- Bronze: 5 verified events, 2% discount, 0.02 trust boost
- Silver: 15 verified events, 5% discount, 0.05 trust boost
- Gold: 30 verified events, 8% discount, 0.08 trust boost
- Platinum: 50 verified events, 12% discount, priority matching
- Legendary: 100 verified events, 15% discount, priority matching
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from kumele_ai.db.models import (
    NFTBadge, NFTBadgeHistory, User, CheckIn, UserMLFeatures
)

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

BADGE_CONFIG = {
    "tiers": {
        "Bronze": {
            "threshold": 5,
            "trust_boost": 0.02,
            "discount_percent": 2.0,
            "priority_matching": False,
            "xp_per_level": 10,
            "max_level": 10
        },
        "Silver": {
            "threshold": 15,
            "trust_boost": 0.05,
            "discount_percent": 5.0,
            "priority_matching": False,
            "xp_per_level": 10,
            "max_level": 10
        },
        "Gold": {
            "threshold": 30,
            "trust_boost": 0.08,
            "discount_percent": 8.0,
            "priority_matching": False,
            "xp_per_level": 15,
            "max_level": 10
        },
        "Platinum": {
            "threshold": 50,
            "trust_boost": 0.12,
            "discount_percent": 12.0,
            "priority_matching": True,
            "xp_per_level": 20,
            "max_level": 10
        },
        "Legendary": {
            "threshold": 100,
            "trust_boost": 0.20,
            "discount_percent": 15.0,
            "priority_matching": True,
            "xp_per_level": 25,
            "max_level": 10
        }
    },
    "tier_order": ["Bronze", "Silver", "Gold", "Platinum", "Legendary"]
}


class NFTBadgeService:
    """
    Service for managing NFT badges.
    
    Badges are earned through verified event attendance and provide:
    - Trust score boosts (affecting matching priority)
    - Price discounts (applied at checkout)
    - Priority matching (for Platinum+ tiers)
    """
    
    def __init__(self):
        self.config = BADGE_CONFIG
    
    # ============================================================
    # BADGE ELIGIBILITY
    # ============================================================
    
    def get_eligible_tier(self, verified_events: int) -> Optional[str]:
        """
        Determine which badge tier a user is eligible for.
        
        Returns the highest tier the user qualifies for, or None.
        """
        eligible_tier = None
        
        for tier in self.config["tier_order"]:
            threshold = self.config["tiers"][tier]["threshold"]
            if verified_events >= threshold:
                eligible_tier = tier
            else:
                break
        
        return eligible_tier
    
    def get_tier_level(self, tier: str) -> int:
        """Get numeric level for tier comparison"""
        try:
            return self.config["tier_order"].index(tier)
        except ValueError:
            return -1
    
    def count_verified_events(
        self,
        db: Session,
        user_id: int
    ) -> int:
        """Count lifetime verified events for a user"""
        return db.query(func.count(CheckIn.id)).filter(
            and_(
                CheckIn.user_id == user_id,
                CheckIn.is_valid == True
            )
        ).scalar() or 0
    
    # ============================================================
    # BADGE MANAGEMENT
    # ============================================================
    
    def check_and_issue_badge(
        self,
        db: Session,
        user_id: int
    ) -> Optional[NFTBadge]:
        """
        Check if user qualifies for a new badge and issue it.
        
        Called after:
        - Successful check-in
        - Event completion
        - Periodic badge review
        """
        # Count verified events
        verified_events = self.count_verified_events(db, user_id)
        
        # Get eligible tier
        eligible_tier = self.get_eligible_tier(verified_events)
        
        if not eligible_tier:
            return None  # Not qualified for any badge
        
        # Get current badge
        current_badge = db.query(NFTBadge).filter(
            and_(
                NFTBadge.user_id == user_id,
                NFTBadge.is_active == True
            )
        ).first()
        
        # Check if upgrade needed
        if current_badge:
            current_level = self.get_tier_level(current_badge.badge_type)
            new_level = self.get_tier_level(eligible_tier)
            
            if new_level <= current_level:
                # No upgrade needed, but update XP
                self._update_badge_xp(db, current_badge, verified_events)
                return current_badge
            
            # Upgrade! Deactivate old badge
            self._deactivate_badge(db, current_badge, "upgraded")
        
        # Issue new badge
        return self._issue_badge(db, user_id, eligible_tier, verified_events)
    
    def _issue_badge(
        self,
        db: Session,
        user_id: int,
        badge_type: str,
        verified_events: int
    ) -> NFTBadge:
        """Issue a new badge to user"""
        tier_config = self.config["tiers"][badge_type]
        
        # Calculate level and XP
        xp = verified_events
        level = min(xp // tier_config["xp_per_level"], tier_config["max_level"])
        
        badge = NFTBadge(
            user_id=user_id,
            badge_type=badge_type,
            level=level,
            experience_points=xp,
            trust_boost=tier_config["trust_boost"],
            price_discount_percent=tier_config["discount_percent"],
            priority_matching=tier_config["priority_matching"],
            earned_reason=f"Achieved {verified_events} verified events",
            is_active=True
        )
        
        db.add(badge)
        db.commit()
        db.refresh(badge)
        
        # Log history
        history = NFTBadgeHistory(
            badge_id=badge.id,
            user_id=user_id,
            action="minted",
            new_level=level,
            new_xp=xp,
            reason=f"Earned {badge_type} badge"
        )
        db.add(history)
        db.commit()
        
        # Update user ML features
        self._update_user_ml_features(db, user_id, badge)
        
        logger.info(f"Issued {badge_type} badge to user {user_id}")
        return badge
    
    def _update_badge_xp(
        self,
        db: Session,
        badge: NFTBadge,
        verified_events: int
    ):
        """Update badge XP and level"""
        tier_config = self.config["tiers"][badge.badge_type]
        
        old_level = badge.level
        old_xp = badge.experience_points
        
        badge.experience_points = verified_events
        new_level = min(verified_events // tier_config["xp_per_level"], tier_config["max_level"])
        
        if new_level > badge.level:
            badge.level = new_level
            
            # Log level up
            history = NFTBadgeHistory(
                badge_id=badge.id,
                user_id=badge.user_id,
                action="upgraded",
                old_level=old_level,
                new_level=new_level,
                old_xp=old_xp,
                new_xp=verified_events,
                reason="Level up from XP gain"
            )
            db.add(history)
        
        db.commit()
    
    def _deactivate_badge(
        self,
        db: Session,
        badge: NFTBadge,
        reason: str
    ):
        """Deactivate a badge"""
        badge.is_active = False
        badge.revoked_at = datetime.utcnow()
        badge.revoked_reason = reason
        
        # Log history
        history = NFTBadgeHistory(
            badge_id=badge.id,
            user_id=badge.user_id,
            action="revoked" if reason != "upgraded" else "upgraded",
            old_level=badge.level,
            old_xp=badge.experience_points,
            reason=reason
        )
        db.add(history)
        db.commit()
    
    def _update_user_ml_features(
        self,
        db: Session,
        user_id: int,
        badge: NFTBadge
    ):
        """Update UserMLFeatures after badge change"""
        user_ml = db.query(UserMLFeatures).filter(
            UserMLFeatures.user_id == user_id
        ).first()
        
        if not user_ml:
            user_ml = UserMLFeatures(user_id=user_id)
            db.add(user_ml)
        
        user_ml.nft_badge_type = badge.badge_type
        user_ml.nft_badge_level = badge.level
        user_ml.nft_trust_boost = badge.trust_boost
        user_ml.last_updated = datetime.utcnow()
        
        db.commit()
    
    # ============================================================
    # BADGE QUERIES
    # ============================================================
    
    def get_user_badge(
        self,
        db: Session,
        user_id: int
    ) -> Optional[NFTBadge]:
        """Get user's current active badge"""
        return db.query(NFTBadge).filter(
            and_(
                NFTBadge.user_id == user_id,
                NFTBadge.is_active == True
            )
        ).first()
    
    def get_user_badge_status(
        self,
        db: Session,
        user_id: int
    ) -> Dict[str, Any]:
        """Get comprehensive badge status for a user"""
        badge = self.get_user_badge(db, user_id)
        verified_events = self.count_verified_events(db, user_id)
        
        # Current status
        current = None
        if badge:
            current = {
                "badge_id": badge.id,
                "type": badge.badge_type,
                "level": badge.level,
                "experience_points": badge.experience_points,
                "trust_boost": badge.trust_boost,
                "discount_percent": badge.price_discount_percent,
                "priority_matching": badge.priority_matching,
                "earned_at": badge.earned_at.isoformat() if badge.earned_at else None
            }
        
        # Next tier progress
        next_tier = None
        events_needed = 0
        progress_percent = 0.0
        
        current_tier_idx = self.get_tier_level(badge.badge_type) if badge else -1
        
        if current_tier_idx < len(self.config["tier_order"]) - 1:
            next_tier_name = self.config["tier_order"][current_tier_idx + 1]
            next_threshold = self.config["tiers"][next_tier_name]["threshold"]
            events_needed = max(next_threshold - verified_events, 0)
            
            if badge:
                current_threshold = self.config["tiers"][badge.badge_type]["threshold"]
                range_size = next_threshold - current_threshold
                progress = verified_events - current_threshold
                progress_percent = min((progress / range_size) * 100, 100)
            else:
                progress_percent = (verified_events / next_threshold) * 100
            
            next_tier = {
                "type": next_tier_name,
                "threshold": next_threshold,
                "events_needed": events_needed,
                "progress_percent": round(progress_percent, 1)
            }
        
        # Badge history
        history = db.query(NFTBadgeHistory).filter(
            NFTBadgeHistory.user_id == user_id
        ).order_by(NFTBadgeHistory.created_at.desc()).limit(10).all()
        
        return {
            "user_id": user_id,
            "verified_events": verified_events,
            "current_badge": current,
            "next_tier": next_tier,
            "history": [
                {
                    "action": h.action,
                    "old_level": h.old_level,
                    "new_level": h.new_level,
                    "reason": h.reason,
                    "created_at": h.created_at.isoformat() if h.created_at else None
                }
                for h in history
            ]
        }
    
    # ============================================================
    # TRUST & MATCHING
    # ============================================================
    
    def get_trust_boost(
        self,
        db: Session,
        user_id: int
    ) -> float:
        """Get trust score boost from NFT badge"""
        badge = self.get_user_badge(db, user_id)
        return badge.trust_boost if badge else 0.0
    
    def get_matching_priority(
        self,
        db: Session,
        user_id: int
    ) -> bool:
        """Check if user has priority matching enabled"""
        badge = self.get_user_badge(db, user_id)
        return badge.priority_matching if badge else False
    
    def get_price_discount(
        self,
        db: Session,
        user_id: int
    ) -> float:
        """Get price discount percentage from NFT badge"""
        badge = self.get_user_badge(db, user_id)
        return badge.price_discount_percent if badge else 0.0
    
    # ============================================================
    # BATCH OPERATIONS
    # ============================================================
    
    def process_pending_badges(
        self,
        db: Session,
        limit: int = 100
    ) -> int:
        """
        Process users who may need badge updates.
        Called by background worker.
        """
        # Find users with verified events but no badge or outdated badge
        users_with_checkins = db.query(
            CheckIn.user_id,
            func.count(CheckIn.id).label("verified_count")
        ).filter(
            CheckIn.is_valid == True
        ).group_by(CheckIn.user_id).having(
            func.count(CheckIn.id) >= self.config["tiers"]["Bronze"]["threshold"]
        ).limit(limit).all()
        
        updated_count = 0
        for user_id, count in users_with_checkins:
            badge = self.check_and_issue_badge(db, user_id)
            if badge:
                updated_count += 1
        
        logger.info(f"Processed {updated_count} badge updates")
        return updated_count


# Singleton instance
nft_badge_service = NFTBadgeService()
