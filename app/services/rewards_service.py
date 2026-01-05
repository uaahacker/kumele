"""
Rewards Service for Rules-Based Gamification.
NOT ML - pure business logic with deterministic, auditable rules.

============================================================================
SPECIFICATION (Verified Implementation)
============================================================================

API: GET /rewards/suggestion?user_id={id}
Returns: current tier(s), progress, available (unredeemed) discounts, reward history

Rules (Last 30 Days Only):
- Count successful events only: attended (not RSVP/no-show) and hosted & completed
- Source of truth: user_activities table (with EventAttendance fallback)

Tiers:
| Tier   | Requirement | Reward        | Stackable |
|--------|-------------|---------------|-----------|
| Bronze | ≥1 event    | No discount   | One-time  |
| Silver | ≥3 events   | 1×4% discount | One-time  |
| Gold   | ≥4 events   | 8% per Gold   | Stackable |

Gold count: floor(total_events_last_30_days / 4)

Discounts:
- Silver: one 4% coupon (max one active)
- Gold: multiple 8% coupons (one per gold stack)
- Coupons auto-issued by daily job, individually redeemable, auditable

Database (Authoritative):
- user_activities: source of truth for event counts
- reward_coupons: Gold multiple rows allowed; Silver max one
- user_reward_progress: computed cache

Workflow:
- Daily job computes eligibility, issues coupons, updates status
- API reads progress + coupons; no claim action (auto-issued)

Non-Goals:
- No ML/prediction
- No recommendations
- No auto-messaging
- No real-time computation (daily job only)
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, update
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
    - Silver: ≥3 created or attended → 4% (one-time, max 1 coupon)
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
    
    # Coupon validity in days
    COUPON_VALIDITY_DAYS = 30

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
        
        SOURCE OF TRUTH: user_activities table
        Fallback: EventAttendance + Event tables
        
        Successful = 
          - activity_type = 'event_attended' AND success = True
          - activity_type = 'event_created' AND success = True (hosted & completed)
        """
        cutoff_date = datetime.utcnow() - timedelta(days=window_days)
        attended_count = 0
        hosted_count = 0
        
        # Try user_activities first (source of truth per spec)
        try:
            # Attended events from user_activities
            attended_query = select(func.count(UserActivity.id)).where(
                and_(
                    UserActivity.user_id == user_id,
                    UserActivity.activity_type == "event_attended",
                    UserActivity.success == True,
                    UserActivity.activity_date >= cutoff_date
                )
            )
            attended_result = await db.execute(attended_query)
            attended_count = attended_result.scalar() or 0
            
            # Hosted/created events from user_activities
            hosted_query = select(func.count(UserActivity.id)).where(
                and_(
                    UserActivity.user_id == user_id,
                    UserActivity.activity_type == "event_created",
                    UserActivity.success == True,
                    UserActivity.activity_date >= cutoff_date
                )
            )
            hosted_result = await db.execute(hosted_query)
            hosted_count = hosted_result.scalar() or 0
            
            # If user_activities has data, use it
            if attended_count > 0 or hosted_count > 0:
                return {
                    "attended": attended_count,
                    "hosted": hosted_count,
                    "total": attended_count + hosted_count
                }
        except Exception as e:
            logger.warning(f"UserActivity query failed: {e}")
        
        # Fallback to EventAttendance/Event tables
        try:
            # Count attended events (checked-in, not just RSVP)
            attended_query = select(func.count(EventAttendance.id)).where(
                and_(
                    EventAttendance.user_id == user_id,
                    EventAttendance.checked_in == True,
                    EventAttendance.checked_in_at >= cutoff_date
                )
            )
            attended_result = await db.execute(attended_query)
            attended_count = attended_result.scalar() or 0
        except Exception as e:
            logger.warning(f"EventAttendance query failed: {e}")
            attended_count = 0
        
        try:
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
        except Exception as e:
            logger.warning(f"Event hosted query failed: {e}")
            hosted_count = 0
        
        return {
            "attended": attended_count,
            "hosted": hosted_count,
            "total": attended_count + hosted_count
        }

    # =========================================================================
    # COUPON MANAGEMENT (Database: reward_coupons)
    # =========================================================================

    @staticmethod
    async def get_available_coupons(
        db: AsyncSession,
        user_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get available (unredeemed, not expired) coupons for a user.
        Reads from reward_coupons table (auditable).
        """
        now = datetime.utcnow()
        
        query = select(RewardCoupon).where(
            and_(
                RewardCoupon.user_id == user_id,
                RewardCoupon.is_redeemed == False,
                or_(
                    RewardCoupon.expires_at == None,
                    RewardCoupon.expires_at > now
                )
            )
        ).order_by(RewardCoupon.issued_at.desc())
        
        result = await db.execute(query)
        coupons = result.scalars().all()
        
        return [
            {
                "coupon_id": str(coupon.coupon_id),
                "discount_percent": float(coupon.discount_value),
                "tier": coupon.status_level,
                "stackable": coupon.stackable,
                "is_redeemed": coupon.is_redeemed,
                "issued_at": coupon.issued_at.isoformat() if coupon.issued_at else None,
                "expires_at": coupon.expires_at.isoformat() if coupon.expires_at else None
            }
            for coupon in coupons
        ]

    @staticmethod
    async def get_coupon_history(
        db: AsyncSession,
        user_id: int,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get user's coupon history (redeemed coupons) - auditable."""
        query = select(RewardCoupon).where(
            and_(
                RewardCoupon.user_id == user_id,
                RewardCoupon.is_redeemed == True
            )
        ).order_by(RewardCoupon.redeemed_at.desc()).limit(limit)
        
        result = await db.execute(query)
        coupons = result.scalars().all()
        
        return [
            {
                "coupon_id": str(coupon.coupon_id),
                "discount_percent": float(coupon.discount_value),
                "tier": coupon.status_level,
                "issued_at": coupon.issued_at.isoformat() if coupon.issued_at else None,
                "redeemed_at": coupon.redeemed_at.isoformat() if coupon.redeemed_at else None,
                "event_id": str(coupon.redeemed_event_id) if coupon.redeemed_event_id else None
            }
            for coupon in coupons
        ]

    @staticmethod
    async def issue_coupon(
        db: AsyncSession,
        user_id: int,
        tier: str,
        discount_value: float,
        stackable: bool = False
    ) -> Optional[RewardCoupon]:
        """
        Issue a new coupon to a user.
        
        Rules:
        - Silver: max one active coupon (check before issuing)
        - Gold: multiple allowed (stackable)
        - Bronze: no discount, no coupon issued
        """
        if tier == "bronze":
            return None  # Bronze has no discount
        
        now = datetime.utcnow()
        expires_at = now + timedelta(days=RewardsService.COUPON_VALIDITY_DAYS)
        
        # Silver uniqueness check: max one active Silver coupon
        if tier == "silver":
            existing_query = select(func.count(RewardCoupon.coupon_id)).where(
                and_(
                    RewardCoupon.user_id == user_id,
                    RewardCoupon.status_level == "silver",
                    RewardCoupon.is_redeemed == False,
                    or_(
                        RewardCoupon.expires_at == None,
                        RewardCoupon.expires_at > now
                    )
                )
            )
            result = await db.execute(existing_query)
            existing_count = result.scalar() or 0
            
            if existing_count > 0:
                logger.debug(f"User {user_id} already has active Silver coupon, skipping")
                return None
        
        # Create coupon
        coupon = RewardCoupon(
            coupon_id=uuid.uuid4(),
            user_id=user_id,
            status_level=tier,
            discount_value=Decimal(str(discount_value)),
            stackable=stackable,
            is_redeemed=False,
            issued_at=now,
            expires_at=expires_at
        )
        
        db.add(coupon)
        logger.info(f"Issued {tier} coupon ({discount_value}%) to user {user_id}")
        
        return coupon

    # =========================================================================
    # MAIN API: GET /rewards/suggestion
    # =========================================================================

    @staticmethod
    async def get_reward_suggestion(
        db: AsyncSession,
        user_id: str,
        include_history: bool = False
    ) -> Dict[str, Any]:
        """
        Get reward suggestion for a user.
        
        Returns:
        - current_status: tier(s), gold_count, counts
        - progress: to next tier
        - available_coupons: unredeemed coupons from DB (auto-issued by daily job)
        - history: (optional) redeemed coupons
        
        Note: Coupons are issued by daily job, not computed here (no real-time computation).
        """
        try:
            user_id_int = int(user_id)
        except ValueError:
            user_id_int = hash(user_id) % 10000000
        
        # Count successful events (source of truth: user_activities)
        event_counts = await RewardsService.count_successful_events(db, user_id_int)
        
        # Calculate tier
        tier_info = RewardsService.calculate_tier(event_counts["total"])
        
        # Calculate progress
        progress_info = RewardsService.calculate_progress(event_counts["total"])
        
        # Get available coupons from DB (issued by daily job)
        available_coupons = await RewardsService.get_available_coupons(db, user_id_int)
        
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
            response["history"] = await RewardsService.get_coupon_history(db, user_id_int)
        
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
            user_id_int = hash(user_id) % 10000000
        
        event_counts = await RewardsService.count_successful_events(db, user_id_int)
        tier_info = RewardsService.calculate_tier(event_counts["total"])
        progress_info = RewardsService.calculate_progress(event_counts["total"])
        
        # Rolling 30-day window
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
        """Get user's reward history (redeemed coupons)."""
        try:
            user_id_int = int(user_id)
        except ValueError:
            user_id_int = hash(user_id) % 10000000
        
        return await RewardsService.get_coupon_history(db, user_id_int)

    # =========================================================================
    # COUPON REDEMPTION
    # =========================================================================

    @staticmethod
    async def redeem_coupon(
        db: AsyncSession,
        coupon_id: str,
        user_id: str,
        event_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Redeem a coupon.
        Updates reward_coupons table (auditable).
        """
        try:
            coupon_uuid = uuid.UUID(coupon_id)
        except ValueError:
            return {"success": False, "message": "Invalid coupon ID format"}
        
        try:
            user_id_int = int(user_id)
        except ValueError:
            user_id_int = hash(user_id) % 10000000
        
        # Get coupon
        query = select(RewardCoupon).where(
            and_(
                RewardCoupon.coupon_id == coupon_uuid,
                RewardCoupon.user_id == user_id_int
            )
        )
        result = await db.execute(query)
        coupon = result.scalar()
        
        if not coupon:
            return {"success": False, "message": "Coupon not found"}
        
        if coupon.is_redeemed:
            return {"success": False, "message": "Coupon already redeemed"}
        
        now = datetime.utcnow()
        if coupon.expires_at and coupon.expires_at < now:
            return {"success": False, "message": "Coupon expired"}
        
        # Redeem (update for audit trail)
        coupon.is_redeemed = True
        coupon.redeemed_at = now
        if event_id:
            try:
                coupon.redeemed_event_id = int(event_id)
            except ValueError:
                pass
        
        logger.info(f"User {user_id} redeemed coupon {coupon_id}")
        
        return {
            "success": True,
            "message": "Coupon redeemed successfully",
            "coupon_id": coupon_id,
            "discount_percent": float(coupon.discount_value),
            "tier": coupon.status_level,
            "event_id": event_id,
            "redeemed_at": now.isoformat()
        }

    @staticmethod
    async def get_user_coupons(
        db: AsyncSession,
        user_id: str,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get user's coupons filtered by status."""
        try:
            user_id_int = int(user_id)
        except ValueError:
            user_id_int = hash(user_id) % 10000000
        
        now = datetime.utcnow()
        
        # Build query
        query = select(RewardCoupon).where(RewardCoupon.user_id == user_id_int)
        
        if status == "active":
            query = query.where(
                and_(
                    RewardCoupon.is_redeemed == False,
                    or_(
                        RewardCoupon.expires_at == None,
                        RewardCoupon.expires_at > now
                    )
                )
            )
        elif status == "redeemed":
            query = query.where(RewardCoupon.is_redeemed == True)
        elif status == "expired":
            query = query.where(
                and_(
                    RewardCoupon.is_redeemed == False,
                    RewardCoupon.expires_at != None,
                    RewardCoupon.expires_at <= now
                )
            )
        
        query = query.order_by(RewardCoupon.issued_at.desc())
        
        result = await db.execute(query)
        coupons = result.scalars().all()
        
        return {
            "user_id": user_id,
            "coupons": [
                {
                    "coupon_id": str(c.coupon_id),
                    "tier": c.status_level,
                    "discount_percent": float(c.discount_value),
                    "stackable": c.stackable,
                    "status": "redeemed" if c.is_redeemed else (
                        "expired" if c.expires_at and c.expires_at <= now else "active"
                    ),
                    "issued_at": c.issued_at.isoformat() if c.issued_at else None,
                    "expires_at": c.expires_at.isoformat() if c.expires_at else None,
                    "redeemed_at": c.redeemed_at.isoformat() if c.redeemed_at else None
                }
                for c in coupons
            ],
            "total_count": len(coupons)
        }

    # =========================================================================
    # DAILY JOB: Compute Eligibility & Issue Coupons
    # =========================================================================

    @staticmethod
    async def compute_daily_rewards(db: AsyncSession) -> Dict[str, Any]:
        """
        Compute daily rewards for all active users.
        Called by cron job / Celery beat.
        
        Workflow (per spec):
        1. Get all users with activity in last 30 days
        2. Calculate tier for each user
        3. Issue new coupons where applicable:
           - Silver: issue 4% if none active (max one)
           - Gold: issue 8% coupons to match gold_count (multiple allowed)
        4. Update user_reward_progress table (cache)
        5. Do NOT delete expired coupons (keep for audit trail)
        
        Non-Goals:
        - No ML/prediction
        - No recommendations  
        - No auto-messaging
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(days=RewardsService.EVALUATION_WINDOW_DAYS)
        
        stats = {
            "users_processed": 0,
            "silver_coupons_issued": 0,
            "gold_coupons_issued": 0,
            "coupons_expired": 0,
            "errors": 0
        }
        
        try:
            # 1. Get active users from user_activities (source of truth)
            active_user_ids = []
            
            try:
                activity_query = select(UserActivity.user_id).where(
                    and_(
                        UserActivity.activity_date >= cutoff,
                        UserActivity.success == True
                    )
                ).distinct()
                
                result = await db.execute(activity_query)
                active_user_ids = [row[0] for row in result.all()]
            except Exception as e:
                logger.warning(f"UserActivity query failed: {e}")
            
            # Fallback: also check EventAttendance if user_activities empty
            if not active_user_ids:
                try:
                    fallback_query = select(EventAttendance.user_id).where(
                        and_(
                            EventAttendance.checked_in == True,
                            EventAttendance.checked_in_at >= cutoff
                        )
                    ).distinct()
                    result = await db.execute(fallback_query)
                    active_user_ids = [row[0] for row in result.all()]
                except Exception as e:
                    logger.warning(f"EventAttendance fallback query failed: {e}")
            
            logger.info(f"Processing rewards for {len(active_user_ids)} active users")
            
            # 2. Process each user
            for user_id in active_user_ids:
                try:
                    await RewardsService._process_user_rewards(db, user_id, stats)
                    stats["users_processed"] += 1
                except Exception as e:
                    logger.error(f"Error processing user {user_id}: {e}")
                    stats["errors"] += 1
            
            # 3. Count expired coupons (for stats, don't delete - audit trail)
            expired_count = await RewardsService._count_expired_coupons(db)
            stats["coupons_expired"] = expired_count
            
            await db.commit()
            
        except Exception as e:
            logger.error(f"Daily rewards computation failed: {e}")
            await db.rollback()
            raise
        
        return {
            "success": True,
            "message": "Daily rewards computed",
            "computed_at": now.isoformat(),
            **stats
        }

    @staticmethod
    async def _process_user_rewards(
        db: AsyncSession,
        user_id: int,
        stats: Dict[str, int]
    ):
        """Process rewards for a single user (called by daily job)."""
        # Count events (source of truth)
        event_counts = await RewardsService.count_successful_events(db, user_id)
        tier_info = RewardsService.calculate_tier(event_counts["total"])
        
        # Issue Silver coupon if eligible (silver or gold tier)
        if tier_info["tier"] in ("silver", "gold"):
            coupon = await RewardsService.issue_coupon(
                db, user_id, "silver",
                discount_value=RewardsService.TIER_DISCOUNTS["silver"],
                stackable=False
            )
            if coupon:
                stats["silver_coupons_issued"] += 1
        
        # Issue Gold coupons to match gold_count (stackable)
        if tier_info["tier"] == "gold" and tier_info["gold_count"] > 0:
            # Count existing active Gold coupons
            existing_gold_query = select(func.count(RewardCoupon.coupon_id)).where(
                and_(
                    RewardCoupon.user_id == user_id,
                    RewardCoupon.status_level == "gold",
                    RewardCoupon.is_redeemed == False,
                    or_(
                        RewardCoupon.expires_at == None,
                        RewardCoupon.expires_at > datetime.utcnow()
                    )
                )
            )
            result = await db.execute(existing_gold_query)
            existing_gold = result.scalar() or 0
            
            # Issue new Gold coupons to reach gold_count
            coupons_to_issue = tier_info["gold_count"] - existing_gold
            for _ in range(max(0, coupons_to_issue)):
                coupon = await RewardsService.issue_coupon(
                    db, user_id, "gold",
                    discount_value=RewardsService.TIER_DISCOUNTS["gold"],
                    stackable=True
                )
                if coupon:
                    stats["gold_coupons_issued"] += 1
        
        # Update user_reward_progress cache
        await RewardsService._update_progress_cache(db, user_id, event_counts, tier_info)

    @staticmethod
    async def _update_progress_cache(
        db: AsyncSession,
        user_id: int,
        event_counts: Dict[str, int],
        tier_info: Dict[str, Any]
    ):
        """Update user_reward_progress table (computed cache)."""
        progress_info = RewardsService.calculate_progress(event_counts["total"])
        
        # Check if exists
        existing = await db.get(UserRewardProgress, user_id)
        
        if existing:
            # Update existing record
            existing.current_tier = tier_info["tier"]
            existing.gold_count = tier_info["gold_count"]
            existing.successful_events_30d = event_counts["total"]
            existing.events_attended_30d = event_counts["attended"]
            existing.events_hosted_30d = event_counts["hosted"]
            existing.next_tier = progress_info["next_tier"]
            existing.events_to_next_tier = progress_info["events_needed"]
            existing.last_computed = datetime.utcnow()
        else:
            # Insert new record
            progress = UserRewardProgress(
                user_id=user_id,
                current_tier=tier_info["tier"],
                gold_count=tier_info["gold_count"],
                successful_events_30d=event_counts["total"],
                events_attended_30d=event_counts["attended"],
                events_hosted_30d=event_counts["hosted"],
                next_tier=progress_info["next_tier"],
                events_to_next_tier=progress_info["events_needed"],
                last_computed=datetime.utcnow()
            )
            db.add(progress)

    @staticmethod
    async def _count_expired_coupons(db: AsyncSession) -> int:
        """Count expired coupons (for stats - not deleted for audit trail)."""
        now = datetime.utcnow()
        
        count_query = select(func.count(RewardCoupon.coupon_id)).where(
            and_(
                RewardCoupon.is_redeemed == False,
                RewardCoupon.expires_at != None,
                RewardCoupon.expires_at <= now
            )
        )
        result = await db.execute(count_query)
        return result.scalar() or 0
