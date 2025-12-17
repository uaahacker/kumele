"""
NFT Badge Intelligence API

Provides endpoints for:
- Badge eligibility checking
- Badge issuance
- Trust score calculations based on badges
- Host priority based on NFT badge level
- Discount eligibility based on badge tier
- Payment reliability tracking
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from kumele_ai.db.database import get_db
from kumele_ai.db.models import (
    User, Event, NFTBadge, NFTBadgeHistory, CheckIn, 
    UserMLFeatures, UserEvent
)
from kumele_ai.services.nft_badge_service import nft_badge_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/nft", tags=["NFT Badge Intelligence"])


# ============================================================
# REQUEST/RESPONSE MODELS
# ============================================================

class BadgeEligibilityResponse(BaseModel):
    user_id: int
    verified_events: int
    current_badge: Optional[str]
    eligible_for: Optional[str]
    next_tier: Optional[str]
    events_until_next: int
    trust_boost: float
    discount_percent: float
    priority_matching: bool


class IssueBadgeRequest(BaseModel):
    user_id: int
    tier: Optional[str] = None  # Auto-determine if not specified


class BadgeResponse(BaseModel):
    id: int
    user_id: int
    tier: str
    level: int
    xp: int
    trust_boost: float
    discount_percent: float
    issued_at: datetime
    expires_at: Optional[datetime]
    is_active: bool
    metadata: Optional[dict]

    class Config:
        from_attributes = True


class TrustScoreResponse(BaseModel):
    user_id: int
    base_trust_score: float
    badge_boost: float
    total_trust_score: float
    badge_tier: Optional[str]
    badge_level: int
    verified_events: int
    attendance_rate: float
    payment_reliability: float


class HostPriorityResponse(BaseModel):
    host_id: int
    badge_tier: Optional[str]
    badge_level: int
    priority_multiplier: float
    trust_boost: float
    price_premium_allowed: float
    priority_matching: bool
    ranking_boost: float


class DiscountEligibilityResponse(BaseModel):
    user_id: int
    badge_tier: Optional[str]
    base_discount_percent: float
    loyalty_bonus_percent: float
    total_discount_percent: float
    max_discount_amount: Optional[float]
    eligibility_expiry: Optional[datetime]


class PaymentReliabilityResponse(BaseModel):
    user_id: int
    total_payments: int
    successful_payments: int
    failed_payments: int
    late_payments: int
    payment_reliability_score: float
    on_time_rate: float
    affects_badge_eligibility: bool


# ============================================================
# BADGE ELIGIBILITY
# ============================================================

@router.get("/badge/eligibility/{user_id}", response_model=BadgeEligibilityResponse)
async def check_badge_eligibility(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Check user's NFT badge eligibility.
    
    Returns:
    - Current badge tier (if any)
    - Eligible tier based on verified events
    - Events needed for next tier
    - Benefits (trust boost, discount, priority)
    """
    try:
        # Count verified events
        verified_count = db.query(func.count(CheckIn.id)).filter(
            and_(
                CheckIn.user_id == user_id,
                CheckIn.is_valid == True
            )
        ).scalar() or 0
    except Exception:
        # Table might not exist or other DB error
        verified_count = 0
    
    try:
        # Get current badge
        current_badge = db.query(NFTBadge).filter(
            and_(
                NFTBadge.user_id == user_id,
                NFTBadge.is_active == True
            )
        ).order_by(NFTBadge.issued_at.desc()).first()
    except Exception:
        current_badge = None
    
    # Determine eligibility
    eligible_tier = nft_badge_service.get_eligible_tier(verified_count)
    
    # Get tier info
    tiers_config = nft_badge_service.config["tiers"]
    tier_order = nft_badge_service.config["tier_order"]
    
    # Calculate next tier info
    next_tier = None
    events_until_next = 0
    
    if eligible_tier:
        try:
            idx = tier_order.index(eligible_tier)
            if idx < len(tier_order) - 1:
                next_tier = tier_order[idx + 1]
                events_until_next = tiers_config[next_tier]["threshold"] - verified_count
        except (ValueError, IndexError):
            pass
    else:
        # Not eligible for any tier yet
        next_tier = tier_order[0]  # Bronze
        events_until_next = tiers_config[next_tier]["threshold"] - verified_count
    
    # Get benefits for eligible tier
    trust_boost = 0.0
    discount_percent = 0.0
    priority_matching = False
    
    if eligible_tier:
        tier_info = tiers_config[eligible_tier]
        trust_boost = tier_info["trust_boost"]
        discount_percent = tier_info["discount_percent"]
        priority_matching = tier_info["priority_matching"]
    
    return BadgeEligibilityResponse(
        user_id=user_id,
        verified_events=verified_count,
        current_badge=current_badge.tier if current_badge else None,
        eligible_for=eligible_tier,
        next_tier=next_tier,
        events_until_next=max(0, events_until_next),
        trust_boost=trust_boost,
        discount_percent=discount_percent,
        priority_matching=priority_matching
    )


@router.post("/badge/issue", response_model=BadgeResponse)
async def issue_badge(
    request: IssueBadgeRequest,
    db: Session = Depends(get_db)
):
    """
    Issue an NFT badge to a user.
    
    If tier is not specified, auto-determines based on verified events.
    
    Creates badge history record for audit trail.
    """
    user = db.query(User).filter(User.id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get verified event count
    verified_count = db.query(func.count(CheckIn.id)).filter(
        and_(
            CheckIn.user_id == request.user_id,
            CheckIn.is_valid == True
        )
    ).scalar() or 0
    
    # Determine tier
    tier = request.tier or nft_badge_service.get_eligible_tier(verified_count)
    
    # Normalize tier name (capitalize first letter)
    if tier:
        tier = tier.capitalize()
    
    if not tier:
        raise HTTPException(
            status_code=400,
            detail=f"User not eligible for any badge tier (has {verified_count} verified events)"
        )
    
    # Get tier config
    tiers_config = nft_badge_service.config["tiers"]
    if tier not in tiers_config:
        valid_tiers = list(tiers_config.keys())
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid tier: {tier}. Valid tiers are: {valid_tiers}"
        )
    
    tier_config = tiers_config[tier]
    
    # Check if user already has this badge
    existing = db.query(NFTBadge).filter(
        and_(
            NFTBadge.user_id == request.user_id,
            NFTBadge.tier == tier,
            NFTBadge.is_active == True
        )
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"User already has active {tier} badge"
        )
    
    # Deactivate old badges
    db.query(NFTBadge).filter(
        and_(
            NFTBadge.user_id == request.user_id,
            NFTBadge.is_active == True
        )
    ).update({"is_active": False})
    
    # Issue new badge
    badge = NFTBadge(
        user_id=request.user_id,
        tier=tier,
        level=1,
        xp=0,
        trust_boost=tier_config["trust_boost"],
        discount_percent=tier_config["discount_percent"],
        is_active=True,
        metadata={
            "verified_events_at_issue": verified_count,
            "issued_reason": "verified_attendance"
        }
    )
    db.add(badge)
    
    # Create history record
    history = NFTBadgeHistory(
        badge_id=0,  # Will update after flush
        user_id=request.user_id,
        action="issued",
        old_tier=None,
        new_tier=tier,
        reason=f"Earned through {verified_count} verified events"
    )
    
    db.flush()
    history.badge_id = badge.id
    db.add(history)
    
    db.commit()
    db.refresh(badge)
    
    return badge


@router.get("/badge/user/{user_id}", response_model=Optional[BadgeResponse])
async def get_user_badge(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get user's current active NFT badge"""
    try:
        badge = db.query(NFTBadge).filter(
            and_(
                NFTBadge.user_id == user_id,
                NFTBadge.is_active == True
            )
        ).first()
    except Exception as e:
        logger.error(f"Error fetching badge for user {user_id}: {e}")
        return None
    
    if not badge:
        return None
    
    return badge


@router.get("/badge/history/{user_id}")
async def get_badge_history(
    user_id: int,
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db)
):
    """Get user's NFT badge history"""
    try:
        history = db.query(NFTBadgeHistory).filter(
            NFTBadgeHistory.user_id == user_id
        ).order_by(NFTBadgeHistory.created_at.desc()).limit(limit).all()
        
        return {
            "user_id": user_id,
            "history": [
                {
                    "id": h.id,
                    "badge_id": h.badge_id,
                    "action": h.action,
                    "old_tier": h.old_tier,
                    "new_tier": h.new_tier,
                    "reason": h.reason,
                    "created_at": h.created_at.isoformat() if h.created_at else None
                }
                for h in history
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching badge history for user {user_id}: {e}")
        return {
            "user_id": user_id,
            "history": [],
            "error": "Could not fetch badge history"
        }


# ============================================================
# TRUST SCORE
# ============================================================

@router.get("/trust-score/{user_id}", response_model=TrustScoreResponse)
async def calculate_trust_score(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Calculate user's trust score including NFT badge boost.
    
    Trust Score = Base Score + Badge Boost
    
    Base score factors:
    - Verified attendance rate
    - Payment reliability
    - Event history reliability
    
    Badge boost: 0.02 (Bronze) to 0.20 (Legendary)
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {e}")
        user = None
    
    # Don't require user to exist - return default trust score
    
    # Get user ML features
    try:
        user_ml = db.query(UserMLFeatures).filter(
            UserMLFeatures.user_id == user_id
        ).first()
    except Exception:
        user_ml = None
    
    # Get badge
    try:
        badge = db.query(NFTBadge).filter(
            and_(
                NFTBadge.user_id == user_id,
                NFTBadge.is_active == True
            )
        ).first()
    except Exception:
        badge = None
    
    # Calculate base trust score
    attendance_rate = 0.0
    if user_ml:
        attendance_rate = user_ml.attendance_rate_90d or 0.0
    
    # Get payment reliability (simplified)
    try:
        total_rsvps = db.query(func.count(UserEvent.id)).filter(
            UserEvent.user_id == user_id
        ).scalar() or 0
        
        attended = db.query(func.count(CheckIn.id)).filter(
            and_(
                CheckIn.user_id == user_id,
                CheckIn.is_valid == True
            )
        ).scalar() or 0
    except Exception:
        total_rsvps = 0
        attended = 0
    
    payment_reliability = attended / max(total_rsvps, 1)
    
    # Base trust score (0-1 scale)
    base_trust = min(1.0, (attendance_rate * 0.5) + (payment_reliability * 0.5))
    
    # Badge boost
    badge_boost = badge.trust_boost if badge else 0.0
    badge_tier = badge.tier if badge else None
    badge_level = badge.level if badge else 0
    
    total_trust = min(1.0, base_trust + badge_boost)
    
    return TrustScoreResponse(
        user_id=user_id,
        base_trust_score=round(base_trust, 4),
        badge_boost=badge_boost,
        total_trust_score=round(total_trust, 4),
        badge_tier=badge_tier,
        badge_level=badge_level,
        verified_events=attended,
        attendance_rate=round(attendance_rate, 4),
        payment_reliability=round(payment_reliability, 4)
    )


# ============================================================
# HOST PRIORITY
# ============================================================

@router.get("/host-priority/{host_id}", response_model=HostPriorityResponse)
async def get_host_priority(
    host_id: int,
    db: Session = Depends(get_db)
):
    """
    Calculate host's priority multiplier based on NFT badge.
    
    NFT Badge affects:
    - Event ranking (higher badge = higher visibility)
    - Price premium allowed (Gold+ can charge more)
    - Priority matching (Platinum+ get featured)
    """
    try:
        host = db.query(User).filter(User.id == host_id).first()
    except Exception:
        host = None
    
    # Don't require host to exist - return default values
    
    # Get host's badge
    try:
        badge = db.query(NFTBadge).filter(
            and_(
                NFTBadge.user_id == host_id,
                NFTBadge.is_active == True
            )
        ).first()
    except Exception:
        badge = None
    
    badge_tier = badge.tier if badge else None
    badge_level = badge.level if badge else 0
    
    # Calculate priority multiplier
    tier_multipliers = {
        "Bronze": 1.0,
        "Silver": 1.1,
        "Gold": 1.25,
        "Platinum": 1.5,
        "Legendary": 2.0
    }
    
    priority_multiplier = tier_multipliers.get(badge_tier, 0.9)  # No badge = 0.9x
    
    # Price premium allowed
    price_premiums = {
        "Bronze": 0.0,
        "Silver": 0.05,
        "Gold": 0.10,
        "Platinum": 0.15,
        "Legendary": 0.20
    }
    price_premium = price_premiums.get(badge_tier, 0.0)
    
    # Trust boost and priority matching
    trust_boost = badge.trust_boost if badge else 0.0
    priority_matching = False
    if badge_tier in ["Platinum", "Legendary"]:
        priority_matching = True
    
    # Ranking boost (1.0 base + level bonus)
    ranking_boost = 1.0 + (badge_level * 0.02) if badge else 0.9
    
    return HostPriorityResponse(
        host_id=host_id,
        badge_tier=badge_tier,
        badge_level=badge_level,
        priority_multiplier=priority_multiplier,
        trust_boost=trust_boost,
        price_premium_allowed=price_premium,
        priority_matching=priority_matching,
        ranking_boost=round(ranking_boost, 2)
    )


# ============================================================
# DISCOUNT ELIGIBILITY
# ============================================================

@router.get("/discount-eligibility/{user_id}", response_model=DiscountEligibilityResponse)
async def check_discount_eligibility(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Check user's discount eligibility based on NFT badge.
    
    Discount tiers:
    - Bronze: 2%
    - Silver: 5%
    - Gold: 8%
    - Platinum: 12%
    - Legendary: 15%
    
    Additional loyalty bonus based on attendance frequency.
    """
    # Get badge
    try:
        badge = db.query(NFTBadge).filter(
            and_(
                NFTBadge.user_id == user_id,
                NFTBadge.is_active == True
            )
        ).first()
    except Exception:
        badge = None
    
    badge_tier = badge.tier if badge else None
    base_discount = badge.discount_percent if badge else 0.0
    
    # Calculate loyalty bonus (0.5% per 10 verified events, max 3%)
    try:
        verified_count = db.query(func.count(CheckIn.id)).filter(
            and_(
                CheckIn.user_id == user_id,
                CheckIn.is_valid == True
            )
        ).scalar() or 0
    except Exception:
        verified_count = 0
    
    loyalty_bonus = min(3.0, (verified_count // 10) * 0.5)
    
    total_discount = base_discount + loyalty_bonus
    
    # Max discount amount (optional cap)
    max_amount = None
    if badge_tier in ["Platinum", "Legendary"]:
        max_amount = 100.0  # $100 max discount
    elif badge_tier:
        max_amount = 50.0  # $50 max for Bronze-Gold
    
    return DiscountEligibilityResponse(
        user_id=user_id,
        badge_tier=badge_tier,
        base_discount_percent=base_discount,
        loyalty_bonus_percent=loyalty_bonus,
        total_discount_percent=total_discount,
        max_discount_amount=max_amount,
        eligibility_expiry=badge.expires_at if badge else None
    )


# ============================================================
# PAYMENT RELIABILITY
# ============================================================

@router.get("/payment-reliability/{user_id}", response_model=PaymentReliabilityResponse)
async def get_payment_reliability(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Get user's payment reliability score.
    
    Tracks:
    - Successful payments
    - Failed payments
    - Late payments
    
    Affects NFT badge eligibility and tier progression.
    """
    # Get user ML features
    try:
        user_ml = db.query(UserMLFeatures).filter(
            UserMLFeatures.user_id == user_id
        ).first()
    except Exception:
        user_ml = None
    
    # Calculate from event history
    try:
        total_paid_rsvps = db.query(func.count(UserEvent.id)).filter(
            and_(
                UserEvent.user_id == user_id,
                UserEvent.rsvp_status.in_(["registered", "attended", "cancelled"])
            )
        ).scalar() or 0
        
        # For now, estimate based on attendance
        successful = db.query(func.count(CheckIn.id)).filter(
            and_(
                CheckIn.user_id == user_id,
                CheckIn.is_valid == True
            )
        ).scalar() or 0
    except Exception:
        total_paid_rsvps = 0
        successful = 0
    
    # Rough estimate of failures
    failed = max(0, total_paid_rsvps - successful)
    
    # Payment reliability score
    reliability_score = successful / max(total_paid_rsvps, 1)
    
    # Check if affects badge eligibility
    affects_eligibility = reliability_score < 0.7  # Below 70% reliability affects eligibility
    
    return PaymentReliabilityResponse(
        user_id=user_id,
        total_payments=total_paid_rsvps,
        successful_payments=successful,
        failed_payments=failed,
        late_payments=0,  # Would need more tracking
        payment_reliability_score=round(reliability_score, 4),
        on_time_rate=round(reliability_score, 4),  # Simplified
        affects_badge_eligibility=affects_eligibility
    )


# ============================================================
# EVENT RANKING WITH NFT
# ============================================================

@router.get("/event-ranking-boost/{event_id}")
async def get_event_ranking_boost(
    event_id: int,
    db: Session = Depends(get_db)
):
    """
    Get event ranking boost based on host's NFT badge.
    
    Returns ranking multiplier for event discovery algorithms.
    """
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
    except Exception as e:
        logger.error(f"Error fetching event {event_id}: {e}")
        event = None
        
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Get host's badge
    try:
        host_badge = db.query(NFTBadge).filter(
            and_(
                NFTBadge.user_id == event.host_id,
                NFTBadge.is_active == True
            )
        ).first()
    except Exception:
        host_badge = None
    
    tier_boosts = {
        "Bronze": 1.05,
        "Silver": 1.10,
        "Gold": 1.20,
        "Platinum": 1.35,
        "Legendary": 1.50
    }
    
    ranking_boost = tier_boosts.get(host_badge.tier if host_badge else None, 1.0)
    
    # Additional boost for badge level
    level_boost = (host_badge.level * 0.01) if host_badge else 0.0
    
    return {
        "event_id": event_id,
        "host_id": event.host_id,
        "host_badge_tier": host_badge.tier if host_badge else None,
        "host_badge_level": host_badge.level if host_badge else 0,
        "base_ranking_boost": ranking_boost,
        "level_boost": round(level_boost, 2),
        "total_ranking_boost": round(ranking_boost + level_boost, 2)
    }
