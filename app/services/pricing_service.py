"""
Dynamic Pricing and Discount Service.
Handles price optimization and discount suggestions.
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from datetime import datetime, timedelta
import logging
import uuid
import math
import statistics

from app.models.database_models import (
    Event, EventStats, PricingHistory, DiscountSuggestion, User
)
from app.config import settings

logger = logging.getLogger(__name__)


class PricingService:
    """Service for dynamic pricing and discount operations."""
    
    # In-memory cache for pricing history (since DB schema doesn't match our needs)
    _pricing_cache: Dict[str, List[Dict[str, Any]]] = {}
    
    # Pricing model parameters
    BASE_DEMAND_MULTIPLIER = 1.0
    TIME_DECAY_FACTOR = 0.05  # Price increases as event approaches
    COMPETITOR_WEIGHT = 0.2
    DEMAND_WEIGHT = 0.3
    CAPACITY_WEIGHT = 0.25
    SEASONALITY_WEIGHT = 0.25
    
    # Discount thresholds
    LOW_BOOKING_THRESHOLD = 0.3  # Less than 30% booked
    HIGH_BOOKING_THRESHOLD = 0.85  # More than 85% booked
    LAST_MINUTE_HOURS = 48  # Hours before event for last-minute pricing

    @staticmethod
    async def get_event_demand_metrics(
        db: AsyncSession,
        event_id: str
    ) -> Dict[str, float]:
        """Get demand metrics for an event."""
        try:
            event_uuid = uuid.UUID(event_id)
            
            # Get event
            event_query = select(Event).where(Event.id == event_uuid)
            result = await db.execute(event_query)
            event = result.scalar_one_or_none()
            
            if not event:
                return {}
            
            # Get event stats
            stats_query = select(EventStats).where(EventStats.event_id == event_uuid)
            stats_result = await db.execute(stats_query)
            stats = stats_result.scalar_one_or_none()
            
            if stats:
                return {
                    "views": stats.view_count,
                    "bookings": stats.booking_count,
                    "capacity": event.capacity if hasattr(event, 'capacity') else 100,
                    "conversion_rate": stats.booking_count / max(1, stats.view_count),
                    "avg_rating": stats.avg_rating
                }
            
            return {
                "views": 0,
                "bookings": 0,
                "capacity": 100,
                "conversion_rate": 0.0,
                "avg_rating": 4.0
            }
            
        except Exception as e:
            logger.error(f"Get demand metrics error: {e}")
            return {}

    @staticmethod
    def calculate_time_factor(event_date: datetime) -> float:
        """
        Calculate time-based pricing factor.
        Price increases as event date approaches.
        """
        now = datetime.utcnow()
        
        if event_date <= now:
            return 1.0
        
        days_until = (event_date - now).days
        
        if days_until > 30:
            return 0.85  # Early bird discount
        elif days_until > 14:
            return 0.95
        elif days_until > 7:
            return 1.0
        elif days_until > 3:
            return 1.1
        elif days_until > 1:
            return 1.15
        else:
            return 1.2  # Last minute premium

    @staticmethod
    def calculate_demand_factor(
        bookings: int,
        capacity: int,
        views: int
    ) -> float:
        """Calculate demand-based pricing factor."""
        booking_rate = bookings / max(1, capacity)
        
        # High demand
        if booking_rate > 0.8:
            return 1.25
        elif booking_rate > 0.6:
            return 1.15
        elif booking_rate > 0.4:
            return 1.05
        elif booking_rate > 0.2:
            return 1.0
        else:
            # Low demand - discount
            return 0.85
    
    @staticmethod
    def calculate_seasonality_factor(event_date: datetime) -> float:
        """Calculate seasonality pricing factor."""
        month = event_date.month
        day_of_week = event_date.weekday()
        
        # Month-based seasonality (simplified)
        month_factors = {
            1: 0.9,   # January (post-holiday)
            2: 0.95,  # February
            3: 1.0,   # March
            4: 1.05,  # April
            5: 1.1,   # May
            6: 1.15,  # June (summer)
            7: 1.2,   # July
            8: 1.15,  # August
            9: 1.0,   # September
            10: 1.05, # October
            11: 1.1,  # November
            12: 1.15  # December
        }
        
        # Weekend premium
        weekend_factor = 1.1 if day_of_week >= 5 else 1.0
        
        return month_factors.get(month, 1.0) * weekend_factor

    @staticmethod
    async def optimize_price(
        db: AsyncSession,
        event_id: str,
        base_price: float,
        event_date: datetime,
        category: Optional[str] = None,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate optimized price for an event.
        Uses multiple factors: time, demand, seasonality, competition.
        """
        # Get demand metrics
        metrics = await PricingService.get_event_demand_metrics(db, event_id)
        
        # Calculate factors
        time_factor = PricingService.calculate_time_factor(event_date)
        demand_factor = PricingService.calculate_demand_factor(
            metrics.get("bookings", 0),
            metrics.get("capacity", 100),
            metrics.get("views", 0)
        )
        seasonality_factor = PricingService.calculate_seasonality_factor(event_date)
        
        # Weighted combination
        combined_factor = (
            PricingService.TIME_DECAY_FACTOR * time_factor +
            PricingService.DEMAND_WEIGHT * demand_factor +
            PricingService.SEASONALITY_WEIGHT * seasonality_factor +
            (1 - PricingService.TIME_DECAY_FACTOR - PricingService.DEMAND_WEIGHT - PricingService.SEASONALITY_WEIGHT)
        )
        
        # Calculate suggested price
        suggested_price = round(base_price * combined_factor, 2)
        
        # Price bounds (not more than 50% deviation)
        min_price = base_price * 0.5
        max_price = base_price * 1.5
        suggested_price = max(min_price, min(max_price, suggested_price))
        
        # Calculate confidence
        data_quality = min(1.0, metrics.get("views", 0) / 100)
        confidence = 0.6 + (0.4 * data_quality)
        
        # Store pricing history in memory cache (DB schema uses different columns)
        # The PricingHistory table has: price, turnout, host_score, city, event_date, revenue
        # But we need: base_price, suggested_price, time_factor, demand_factor, etc.
        # Using in-memory cache for demo purposes
        history_entry = {
            "event_id": event_id,
            "base_price": base_price,
            "suggested_price": suggested_price,
            "time_factor": time_factor,
            "demand_factor": demand_factor,
            "seasonality_factor": seasonality_factor,
            "final_factor": combined_factor,
            "calculated_at": datetime.utcnow().isoformat()
        }
        
        # Store in class-level cache
        if event_id not in PricingService._pricing_cache:
            PricingService._pricing_cache[event_id] = []
        PricingService._pricing_cache[event_id].append(history_entry)
        # Keep only last 100 entries per event
        PricingService._pricing_cache[event_id] = PricingService._pricing_cache[event_id][-100:]
        
        return {
            "event_id": event_id,
            "base_price": base_price,
            "suggested_price": suggested_price,
            "price_change_percent": round((combined_factor - 1) * 100, 1),
            "factors": {
                "time": round(time_factor, 3),
                "demand": round(demand_factor, 3),
                "seasonality": round(seasonality_factor, 3),
                "combined": round(combined_factor, 3)
            },
            "metrics": {
                "booking_rate": round(metrics.get("bookings", 0) / max(1, metrics.get("capacity", 100)), 2),
                "views": metrics.get("views", 0),
                "days_until_event": (event_date - datetime.utcnow()).days if event_date > datetime.utcnow() else 0
            },
            "confidence": round(confidence, 2),
            "recommendation": PricingService._get_price_recommendation(combined_factor)
        }

    @staticmethod
    def _get_price_recommendation(factor: float) -> str:
        """Get human-readable pricing recommendation."""
        if factor >= 1.2:
            return "High demand - consider increasing price"
        elif factor >= 1.1:
            return "Good demand - moderate price increase suggested"
        elif factor >= 0.95:
            return "Stable demand - maintain current pricing"
        elif factor >= 0.85:
            return "Low demand - consider promotional discount"
        else:
            return "Very low demand - significant discount recommended"

    @staticmethod
    async def suggest_discount(
        db: AsyncSession,
        user_id: Optional[str] = None,
        event_id: Optional[str] = None,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate personalized discount suggestions.
        Based on user behavior, event performance, and business rules.
        """
        suggestions = []
        
        # User-based discounts
        if user_id:
            user_discounts = await PricingService._get_user_discounts(db, user_id)
            suggestions.extend(user_discounts)
        
        # Event-based discounts
        if event_id:
            event_discounts = await PricingService._get_event_discounts(db, event_id)
            suggestions.extend(event_discounts)
        
        # Category-based discounts
        if category:
            category_discounts = await PricingService._get_category_discounts(db, category)
            suggestions.extend(category_discounts)
        
        # If no specific filters, get general promotions
        if not suggestions:
            suggestions = await PricingService._get_general_promotions(db)
        
        # Sort by relevance score
        suggestions.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        
        return {
            "suggestions": suggestions[:5],  # Top 5 suggestions
            "user_id": user_id,
            "event_id": event_id,
            "generated_at": datetime.utcnow().isoformat()
        }

    @staticmethod
    async def _get_user_discounts(
        db: AsyncSession,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """Get personalized discounts based on user profile."""
        discounts = []
        
        try:
            user_uuid = uuid.UUID(user_id)
            
            # Get user
            user_query = select(User).where(User.id == user_uuid)
            result = await db.execute(user_query)
            user = result.scalar_one_or_none()
            
            if not user:
                return []
            
            # Check if new user (first 30 days)
            if user.created_at:
                days_since_signup = (datetime.utcnow() - user.created_at).days
                
                if days_since_signup <= 30:
                    discounts.append({
                        "type": "new_user",
                        "code": "WELCOME15",
                        "discount_percent": 15,
                        "description": "Welcome discount for new users",
                        "valid_until": (datetime.utcnow() + timedelta(days=30-days_since_signup)).isoformat(),
                        "relevance_score": 0.9
                    })
            
            # Check user activity for re-engagement
            # This would check last activity date
            discounts.append({
                "type": "loyalty",
                "code": "LOYAL10",
                "discount_percent": 10,
                "description": "Loyalty reward for returning users",
                "valid_until": (datetime.utcnow() + timedelta(days=14)).isoformat(),
                "relevance_score": 0.7
            })
            
        except Exception as e:
            logger.error(f"Get user discounts error: {e}")
        
        return discounts

    @staticmethod
    async def _get_event_discounts(
        db: AsyncSession,
        event_id: str
    ) -> List[Dict[str, Any]]:
        """Get discounts based on event performance."""
        discounts = []
        
        try:
            event_uuid = uuid.UUID(event_id)
            
            # Get event
            event_query = select(Event).where(Event.id == event_uuid)
            result = await db.execute(event_query)
            event = result.scalar_one_or_none()
            
            if not event:
                return []
            
            # Get metrics
            metrics = await PricingService.get_event_demand_metrics(db, event_id)
            
            booking_rate = metrics.get("bookings", 0) / max(1, metrics.get("capacity", 100))
            
            # Low booking - promotional discount
            if booking_rate < PricingService.LOW_BOOKING_THRESHOLD:
                discount_pct = int(20 - (booking_rate * 30))
                discounts.append({
                    "type": "low_demand",
                    "event_id": event_id,
                    "discount_percent": discount_pct,
                    "description": f"Limited spots remaining - {discount_pct}% off",
                    "valid_until": (datetime.utcnow() + timedelta(days=7)).isoformat(),
                    "relevance_score": 0.85
                })
            
            # Check if event is soon (last-minute deal)
            if hasattr(event, 'event_date') and event.event_date:
                hours_until = (event.event_date - datetime.utcnow()).total_seconds() / 3600
                
                if 0 < hours_until <= PricingService.LAST_MINUTE_HOURS and booking_rate < 0.7:
                    discounts.append({
                        "type": "last_minute",
                        "event_id": event_id,
                        "discount_percent": 25,
                        "description": "Last-minute deal - 25% off!",
                        "valid_until": event.event_date.isoformat(),
                        "relevance_score": 0.95
                    })
            
        except Exception as e:
            logger.error(f"Get event discounts error: {e}")
        
        return discounts

    @staticmethod
    async def _get_category_discounts(
        db: AsyncSession,
        category: str
    ) -> List[Dict[str, Any]]:
        """Get category-specific promotions."""
        # Category promotions (would be configured in admin)
        category_promos = {
            "outdoor": {
                "type": "category_promo",
                "code": "OUTDOOR20",
                "discount_percent": 20,
                "description": "Outdoor adventure discount",
                "relevance_score": 0.75
            },
            "workshop": {
                "type": "category_promo",
                "code": "LEARN15",
                "discount_percent": 15,
                "description": "Workshop learning discount",
                "relevance_score": 0.75
            },
            "social": {
                "type": "category_promo",
                "code": "SOCIAL10",
                "discount_percent": 10,
                "description": "Social meetup discount",
                "relevance_score": 0.7
            }
        }
        
        promo = category_promos.get(category.lower())
        if promo:
            promo["valid_until"] = (datetime.utcnow() + timedelta(days=30)).isoformat()
            return [promo]
        
        return []

    @staticmethod
    async def _get_general_promotions(
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Get general platform promotions."""
        return [
            {
                "type": "general",
                "code": "KUMELE10",
                "discount_percent": 10,
                "description": "Platform-wide 10% discount",
                "valid_until": (datetime.utcnow() + timedelta(days=30)).isoformat(),
                "relevance_score": 0.5
            },
            {
                "type": "referral",
                "code": "REFER20",
                "discount_percent": 20,
                "description": "Refer a friend and both get 20% off",
                "valid_until": (datetime.utcnow() + timedelta(days=90)).isoformat(),
                "relevance_score": 0.6
            }
        ]

    @staticmethod
    async def get_pricing_history(
        db: AsyncSession,
        event_id: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get pricing history for an event from in-memory cache."""
        try:
            since = datetime.utcnow() - timedelta(days=days)
            
            # Get from in-memory cache
            cached_history = PricingService._pricing_cache.get(event_id, [])
            
            # Filter by date
            filtered = []
            for h in cached_history:
                calc_time = datetime.fromisoformat(h["calculated_at"]) if isinstance(h["calculated_at"], str) else h["calculated_at"]
                if calc_time >= since:
                    filtered.append({
                        "calculated_at": h["calculated_at"] if isinstance(h["calculated_at"], str) else h["calculated_at"].isoformat(),
                        "base_price": h["base_price"],
                        "suggested_price": h["suggested_price"],
                        "factors": {
                            "time": h["time_factor"],
                            "demand": h["demand_factor"],
                            "seasonality": h["seasonality_factor"],
                            "combined": h["final_factor"]
                        }
                    })
            
            # Return sorted by most recent first
            return sorted(filtered, key=lambda x: x["calculated_at"], reverse=True)
            
        except Exception as e:
            logger.error(f"Get pricing history error: {e}")
            return []
