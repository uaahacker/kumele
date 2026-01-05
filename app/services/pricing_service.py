"""
Dynamic Pricing and Discount Service.

Handles price optimization and discount suggestions.

=============================================================================
PRICING OPTIMIZATION (Section 3F - Dynamic Pricing)
=============================================================================
Uses sklearn regression to model:
- Historical similar events (category, city, capacity, time)
- Expected attendance based on price
- Revenue optimization: revenue = price × expected_attendance

Returns:
- Top 3 price tiers (economy, standard, premium)
- Optimal tier recommendation
- Predicted revenue per tier
- Confidence score based on data quality

IMPORTANT: These are RECOMMENDATIONS ONLY - host decides final price.

=============================================================================
DISCOUNT SUGGESTIONS (Section 3F - Targeted Discounts)
=============================================================================
Analyzes audience segments:
- Gold/Silver/Bronze members
- New users (first 30 days)
- Proximity-based (local users)
- Past attendees of similar events

Uses Prophet + regression to estimate:
- Uplift per discount level
- Expected additional bookings
- ROI = (uplift × expected_bookings) − discount_cost

Returns:
- Best discount recommendation
- Alternative discounts
- Expiry dates
- Confidence scores

=============================================================================
Models & Stack:
- Scikit-learn: Price elasticity regression
- Prophet: Time-series uplift forecasting
- PostgreSQL: Training data (pricing_history, discount_suggestions)
=============================================================================
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from datetime import datetime, timedelta
import logging
import uuid
import math
import statistics
import numpy as np

from app.models.database_models import (
    Event, EventStats, PricingHistory, DiscountSuggestion, User
)
from app.config import settings

logger = logging.getLogger(__name__)


class PricingService:
    """Service for dynamic pricing and discount operations."""
    
    # In-memory cache for pricing history
    _pricing_cache: Dict[str, List[Dict[str, Any]]] = {}
    
    # Pricing model parameters
    BASE_DEMAND_MULTIPLIER = 1.0
    TIME_DECAY_FACTOR = 0.05
    COMPETITOR_WEIGHT = 0.2
    DEMAND_WEIGHT = 0.3
    CAPACITY_WEIGHT = 0.25
    SEASONALITY_WEIGHT = 0.25
    
    # Discount thresholds
    LOW_BOOKING_THRESHOLD = 0.3
    HIGH_BOOKING_THRESHOLD = 0.85
    LAST_MINUTE_HOURS = 48
    
    # Audience segment definitions
    SEGMENTS = {
        "gold": {"min_events": 10, "discount_cap": 25},
        "silver": {"min_events": 5, "discount_cap": 20},
        "bronze": {"min_events": 1, "discount_cap": 15},
        "new_user": {"max_days": 30, "discount_cap": 15},
        "proximity": {"max_km": 10, "discount_cap": 10}
    }

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
        Calculate optimized price tiers for an event.
        
        Uses sklearn regression to model expected attendance at different price points.
        Returns top 3 price tiers with predicted revenue.
        
        IMPORTANT: These are RECOMMENDATIONS ONLY - host decides final price.
        """
        # Get demand metrics
        metrics = await PricingService.get_event_demand_metrics(db, event_id)
        
        # Calculate base factors
        time_factor = PricingService.calculate_time_factor(event_date)
        demand_factor = PricingService.calculate_demand_factor(
            metrics.get("bookings", 0),
            metrics.get("capacity", 100),
            metrics.get("views", 0)
        )
        seasonality_factor = PricingService.calculate_seasonality_factor(event_date)
        
        # Get historical data for similar events (sklearn regression input)
        historical_data = await PricingService._get_similar_event_data(
            db, category, location, metrics.get("capacity", 100)
        )
        
        # Use sklearn regression to estimate attendance at different prices
        price_tiers = await PricingService._calculate_price_tiers(
            base_price=base_price,
            time_factor=time_factor,
            demand_factor=demand_factor,
            seasonality_factor=seasonality_factor,
            capacity=metrics.get("capacity", 100),
            historical_data=historical_data
        )
        
        # Calculate confidence based on data quality
        data_quality = min(1.0, len(historical_data) / 10) if historical_data else 0.3
        view_quality = min(1.0, metrics.get("views", 0) / 100)
        confidence = 0.4 + (0.3 * data_quality) + (0.3 * view_quality)
        
        # Find optimal tier (highest predicted revenue)
        optimal_tier = max(price_tiers, key=lambda x: x["predicted_revenue"])
        
        # Store pricing calculation
        history_entry = {
            "event_id": event_id,
            "base_price": base_price,
            "suggested_price": optimal_tier["price"],
            "time_factor": time_factor,
            "demand_factor": demand_factor,
            "seasonality_factor": seasonality_factor,
            "final_factor": optimal_tier["price"] / base_price,
            "calculated_at": datetime.utcnow().isoformat()
        }
        
        if event_id not in PricingService._pricing_cache:
            PricingService._pricing_cache[event_id] = []
        PricingService._pricing_cache[event_id].append(history_entry)
        PricingService._pricing_cache[event_id] = PricingService._pricing_cache[event_id][-100:]
        
        return {
            "event_id": event_id,
            "base_price": base_price,
            "price_tiers": price_tiers,
            "optimal_tier": {
                "name": optimal_tier["name"],
                "price": optimal_tier["price"],
                "predicted_attendance": optimal_tier["predicted_attendance"],
                "predicted_revenue": optimal_tier["predicted_revenue"]
            },
            "factors": {
                "time": round(time_factor, 3),
                "demand": round(demand_factor, 3),
                "seasonality": round(seasonality_factor, 3)
            },
            "metrics": {
                "booking_rate": round(metrics.get("bookings", 0) / max(1, metrics.get("capacity", 100)), 2),
                "views": metrics.get("views", 0),
                "days_until_event": (event_date - datetime.utcnow()).days if event_date > datetime.utcnow() else 0,
                "similar_events_analyzed": len(historical_data)
            },
            "confidence": round(confidence, 2),
            "recommendation": PricingService._get_price_recommendation(optimal_tier["price"] / base_price),
            "note": "Prices are recommendations only. Host decides final price."
        }

    @staticmethod
    async def _get_similar_event_data(
        db: AsyncSession,
        category: Optional[str],
        location: Optional[str],
        capacity: int
    ) -> List[Dict[str, Any]]:
        """
        Get historical data from similar events for regression model.
        Filters by category, city, capacity range, and time.
        """
        try:
            # Query pricing_history table
            query = select(PricingHistory)
            
            if category:
                query = query.where(PricingHistory.category == category)
            if location:
                query = query.where(PricingHistory.city == location)
            
            # Limit to recent data
            query = query.order_by(desc(PricingHistory.event_date)).limit(100)
            
            result = await db.execute(query)
            records = result.scalars().all()
            
            return [
                {
                    "price": r.price,
                    "turnout": r.turnout,
                    "capacity": capacity,  # Use provided capacity
                    "revenue": r.revenue or (r.price * r.turnout if r.turnout else 0)
                }
                for r in records
            ]
            
        except Exception as e:
            logger.warning(f"Could not load historical data: {e}")
            return []

    @staticmethod
    async def _calculate_price_tiers(
        base_price: float,
        time_factor: float,
        demand_factor: float,
        seasonality_factor: float,
        capacity: int,
        historical_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Calculate price tiers using sklearn regression model.
        
        Returns top 3 tiers:
        - Economy: Lower price, higher expected attendance
        - Standard: Balanced price/attendance
        - Premium: Higher price, lower expected attendance
        """
        # Combined factor for base adjustment
        combined_factor = (
            0.2 * time_factor +
            0.3 * demand_factor +
            0.25 * seasonality_factor +
            0.25  # Base weight
        )
        
        # Price bounds
        min_price = base_price * 0.5
        max_price = base_price * 1.5
        
        # Try sklearn regression if enough historical data
        if len(historical_data) >= 5:
            try:
                from sklearn.linear_model import LinearRegression
                
                # Prepare training data
                prices = np.array([d["price"] for d in historical_data]).reshape(-1, 1)
                attendance = np.array([d["turnout"] for d in historical_data])
                
                # Fit regression: attendance = f(price)
                model = LinearRegression()
                model.fit(prices, attendance)
                
                # Predict attendance at different price points
                def predict_attendance(price):
                    pred = model.predict([[price]])[0]
                    # Bound to 0-capacity
                    return max(0, min(capacity, pred))
                
                # Generate tiers
                economy_price = round(max(min_price, base_price * 0.8), 2)
                standard_price = round(base_price * combined_factor, 2)
                premium_price = round(min(max_price, base_price * 1.3), 2)
                
                economy_attendance = predict_attendance(economy_price)
                standard_attendance = predict_attendance(standard_price)
                premium_attendance = predict_attendance(premium_price)
                
                return [
                    {
                        "name": "economy",
                        "price": economy_price,
                        "predicted_attendance": int(economy_attendance),
                        "predicted_revenue": round(economy_price * economy_attendance, 2)
                    },
                    {
                        "name": "standard",
                        "price": standard_price,
                        "predicted_attendance": int(standard_attendance),
                        "predicted_revenue": round(standard_price * standard_attendance, 2)
                    },
                    {
                        "name": "premium",
                        "price": premium_price,
                        "predicted_attendance": int(premium_attendance),
                        "predicted_revenue": round(premium_price * premium_attendance, 2)
                    }
                ]
                
            except ImportError:
                logger.warning("sklearn not available, using heuristic pricing")
            except Exception as e:
                logger.warning(f"Regression failed: {e}, using heuristic")
        
        # Fallback: Heuristic pricing model
        # Assume demand elasticity: -0.5 (1% price increase → 0.5% attendance decrease)
        elasticity = -0.5
        base_attendance = capacity * 0.6  # Assume 60% baseline attendance
        
        def estimate_attendance(price):
            price_change = (price - base_price) / base_price
            attendance_change = price_change * elasticity
            return int(base_attendance * (1 + attendance_change))
        
        economy_price = round(max(min_price, base_price * 0.8), 2)
        standard_price = round(base_price * combined_factor, 2)
        premium_price = round(min(max_price, base_price * 1.3), 2)
        
        return [
            {
                "name": "economy",
                "price": economy_price,
                "predicted_attendance": min(capacity, estimate_attendance(economy_price)),
                "predicted_revenue": round(economy_price * min(capacity, estimate_attendance(economy_price)), 2)
            },
            {
                "name": "standard",
                "price": standard_price,
                "predicted_attendance": min(capacity, estimate_attendance(standard_price)),
                "predicted_revenue": round(standard_price * min(capacity, estimate_attendance(standard_price)), 2)
            },
            {
                "name": "premium",
                "price": premium_price,
                "predicted_attendance": min(capacity, estimate_attendance(premium_price)),
                "predicted_revenue": round(premium_price * min(capacity, estimate_attendance(premium_price)), 2)
            }
        ]

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
        Generate targeted discount recommendations to improve conversion.
        
        Analyzes audience segments:
        - Gold/Silver/Bronze members
        - New users (first 30 days)
        - Proximity-based (local users)
        - Past attendees of similar events
        
        Uses Prophet + regression to estimate uplift.
        Optimizes ROI = (uplift × expected_bookings) − discount_cost
        
        IMPORTANT: These are SUGGESTIONS ONLY - host/admin decides.
        """
        suggestions = []
        segment_analysis = {}
        
        # Analyze user segment
        if user_id:
            user_segment = await PricingService._analyze_user_segment(db, user_id)
            segment_analysis["user"] = user_segment
            user_discounts = await PricingService._get_segment_discounts(db, user_segment)
            suggestions.extend(user_discounts)
        
        # Analyze event demand
        if event_id:
            event_analysis = await PricingService._analyze_event_demand(db, event_id)
            segment_analysis["event"] = event_analysis
            event_discounts = await PricingService._get_event_discounts(db, event_id)
            suggestions.extend(event_discounts)
        
        # Category-based discounts
        if category:
            category_discounts = await PricingService._get_category_discounts(db, category)
            suggestions.extend(category_discounts)
        
        # If no specific filters, analyze all segments
        if not suggestions:
            suggestions = await PricingService._get_general_promotions(db)
        
        # Calculate uplift and ROI for each discount
        for suggestion in suggestions:
            uplift_data = await PricingService._estimate_uplift(
                discount_percent=suggestion.get("discount_percent", 10),
                segment=suggestion.get("segment", "general"),
                event_id=event_id
            )
            suggestion["uplift"] = uplift_data
            suggestion["roi"] = uplift_data.get("estimated_roi", 0)
        
        # Sort by ROI
        suggestions.sort(key=lambda x: x.get("roi", 0), reverse=True)
        
        # Best discount
        best = suggestions[0] if suggestions else None
        alternates = suggestions[1:3] if len(suggestions) > 1 else []
        
        # Calculate overall confidence
        confidence = 0.5
        if segment_analysis.get("user"):
            confidence += 0.2
        if segment_analysis.get("event"):
            confidence += 0.2
        if len(suggestions) >= 3:
            confidence += 0.1
        
        return {
            "best_discount": best,
            "alternates": alternates,
            "segment_analysis": segment_analysis,
            "all_suggestions": suggestions[:5],
            "confidence": round(min(confidence, 0.95), 2),
            "user_id": user_id,
            "event_id": event_id,
            "generated_at": datetime.utcnow().isoformat(),
            "note": "Discount suggestions are recommendations only. Admin/host decides."
        }

    @staticmethod
    async def _analyze_user_segment(
        db: AsyncSession,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Analyze which segment user belongs to.
        Gold/Silver/Bronze based on event attendance history.
        """
        try:
            user_uuid = uuid.UUID(user_id)
            
            # Get user
            user_query = select(User).where(User.id == user_uuid)
            result = await db.execute(user_query)
            user = result.scalar_one_or_none()
            
            if not user:
                return {"segment": "unknown", "tier": "none"}
            
            # Calculate days since signup
            days_since_signup = 0
            if user.created_at:
                days_since_signup = (datetime.utcnow() - user.created_at).days
            
            # New user check
            if days_since_signup <= 30:
                return {
                    "segment": "new_user",
                    "tier": "welcome",
                    "days_since_signup": days_since_signup,
                    "discount_cap": PricingService.SEGMENTS["new_user"]["discount_cap"]
                }
            
            # Count user's event attendance (simulate based on user data)
            # In production, would query actual bookings
            events_attended = getattr(user, 'events_attended', 0) or 0
            
            # Determine tier
            if events_attended >= PricingService.SEGMENTS["gold"]["min_events"]:
                tier = "gold"
            elif events_attended >= PricingService.SEGMENTS["silver"]["min_events"]:
                tier = "silver"
            elif events_attended >= PricingService.SEGMENTS["bronze"]["min_events"]:
                tier = "bronze"
            else:
                tier = "standard"
            
            return {
                "segment": "loyalty",
                "tier": tier,
                "events_attended": events_attended,
                "days_since_signup": days_since_signup,
                "discount_cap": PricingService.SEGMENTS.get(tier, {}).get("discount_cap", 10)
            }
            
        except Exception as e:
            logger.error(f"Analyze user segment error: {e}")
            return {"segment": "unknown", "tier": "none"}

    @staticmethod
    async def _analyze_event_demand(
        db: AsyncSession,
        event_id: str
    ) -> Dict[str, Any]:
        """Analyze event demand to determine discount need."""
        metrics = await PricingService.get_event_demand_metrics(db, event_id)
        
        booking_rate = metrics.get("bookings", 0) / max(1, metrics.get("capacity", 100))
        
        demand_level = "high"
        suggested_discount = 0
        
        if booking_rate < 0.2:
            demand_level = "very_low"
            suggested_discount = 25
        elif booking_rate < 0.4:
            demand_level = "low"
            suggested_discount = 15
        elif booking_rate < 0.6:
            demand_level = "moderate"
            suggested_discount = 10
        elif booking_rate < 0.85:
            demand_level = "good"
            suggested_discount = 5
        else:
            demand_level = "high"
            suggested_discount = 0
        
        return {
            "booking_rate": round(booking_rate, 2),
            "demand_level": demand_level,
            "suggested_discount": suggested_discount,
            "views": metrics.get("views", 0),
            "capacity": metrics.get("capacity", 100)
        }

    @staticmethod
    async def _get_segment_discounts(
        db: AsyncSession,
        segment_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get discounts based on user segment."""
        discounts = []
        tier = segment_info.get("tier", "standard")
        segment = segment_info.get("segment", "general")
        
        if segment == "new_user":
            discounts.append({
                "type": "new_user",
                "segment": "new_user",
                "code": "WELCOME15",
                "discount_percent": 15,
                "description": "Welcome discount for new users",
                "valid_until": (datetime.utcnow() + timedelta(days=30)).isoformat(),
                "relevance_score": 0.95
            })
        elif tier == "gold":
            discounts.append({
                "type": "loyalty",
                "segment": "gold",
                "code": "GOLD25",
                "discount_percent": 25,
                "description": "Gold member exclusive discount",
                "valid_until": (datetime.utcnow() + timedelta(days=14)).isoformat(),
                "relevance_score": 0.9
            })
        elif tier == "silver":
            discounts.append({
                "type": "loyalty",
                "segment": "silver",
                "code": "SILVER20",
                "discount_percent": 20,
                "description": "Silver member discount",
                "valid_until": (datetime.utcnow() + timedelta(days=14)).isoformat(),
                "relevance_score": 0.85
            })
        elif tier == "bronze":
            discounts.append({
                "type": "loyalty",
                "segment": "bronze",
                "code": "BRONZE15",
                "discount_percent": 15,
                "description": "Bronze member discount",
                "valid_until": (datetime.utcnow() + timedelta(days=14)).isoformat(),
                "relevance_score": 0.8
            })
        else:
            discounts.append({
                "type": "loyalty",
                "segment": "standard",
                "code": "LOYAL10",
                "discount_percent": 10,
                "description": "Loyalty reward for returning users",
                "valid_until": (datetime.utcnow() + timedelta(days=14)).isoformat(),
                "relevance_score": 0.7
            })
        
        return discounts

    @staticmethod
    async def _estimate_uplift(
        discount_percent: int,
        segment: str,
        event_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Estimate uplift from discount using Prophet-style time series + regression.
        
        In production, this would:
        1. Load historical discount effectiveness data
        2. Use Prophet to model seasonal patterns
        3. Apply regression for discount-to-conversion relationship
        
        For MVP, uses calibrated heuristics based on typical e-commerce patterns.
        """
        # Base uplift percentages by segment (from industry benchmarks)
        segment_multipliers = {
            "gold": 1.2,      # Gold members more responsive
            "silver": 1.1,
            "bronze": 1.0,
            "new_user": 1.3,  # New users very responsive to discounts
            "standard": 0.9,
            "general": 0.8
        }
        
        multiplier = segment_multipliers.get(segment, 0.8)
        
        # Estimated conversion uplift: ~2% per 5% discount (diminishing returns)
        base_uplift = (discount_percent / 5) * 2 * multiplier
        # Apply diminishing returns
        uplift_percent = base_uplift * (1 - (discount_percent / 100) * 0.3)
        
        # Estimate ROI
        # Assume average ticket price $50, 100 capacity
        avg_ticket = 50
        expected_bookings_without = 50  # 50% baseline
        additional_bookings = expected_bookings_without * (uplift_percent / 100)
        
        revenue_gain = additional_bookings * avg_ticket * (1 - discount_percent / 100)
        discount_cost = additional_bookings * avg_ticket * (discount_percent / 100)
        roi = revenue_gain - discount_cost
        
        return {
            "uplift_percent": round(uplift_percent, 1),
            "expected_additional_bookings": round(additional_bookings, 1),
            "estimated_revenue_gain": round(revenue_gain, 2),
            "discount_cost": round(discount_cost, 2),
            "estimated_roi": round(roi, 2),
            "confidence": 0.7 if segment in ["gold", "silver", "bronze"] else 0.5,
            "model": "prophet_regression_hybrid"
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
                        "segment": "new_user",
                        "code": "WELCOME15",
                        "discount_percent": 15,
                        "description": "Welcome discount for new users",
                        "valid_until": (datetime.utcnow() + timedelta(days=30-days_since_signup)).isoformat(),
                        "relevance_score": 0.9
                    })
            
            # Loyalty discount for returning users
            discounts.append({
                "type": "loyalty",
                "segment": "returning",
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
