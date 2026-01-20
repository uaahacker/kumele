"""
Pricing Service - Dynamic Pricing Optimization Engine

Enhanced with:
- No-Show Probability Integration: Adjust prices based on predicted attendance
- Host Tier Influence: Premium hosts can command higher prices
- Verified Attendance Integration: Discount for verified attendees
- NFT Badge Discounts: Badge holders get automatic discounts
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor

from kumele_ai.db.models import (
    Event, PricingHistory, DiscountSuggestion, UserEvent, 
    RewardCoupon, User, HostRating,
    UserMLFeatures, NFTBadge, EventMLFeatures, CheckIn
)

logger = logging.getLogger(__name__)


# ============================================================
# PRICING CONFIGURATION
# ============================================================

PRICING_CONFIG = {
    # Base pricing tiers
    "min_price": 5.0,
    "max_price": 500.0,
    "default_price": 25.0,
    
    # Host tier price multipliers
    "host_tier_multipliers": {
        "Bronze": 1.0,
        "Silver": 1.10,
        "Gold": 1.25,
    },
    
    # No-show adjustments
    "no_show_overbooking_thresholds": {
        0.10: 1.05,  # 10% no-show → overbook by 5%
        0.20: 1.10,  # 20% no-show → overbook by 10%
        0.30: 1.15,  # 30% no-show → overbook by 15%
        0.40: 1.20,  # 40% no-show → overbook by 20%
    },
    
    # NFT badge discounts
    "nft_badge_discounts": {
        "Bronze": 0.02,      # 2% discount
        "Silver": 0.05,      # 5% discount
        "Gold": 0.08,        # 8% discount
        "Platinum": 0.12,    # 12% discount
        "Legendary": 0.15,   # 15% discount
    },
    
    # Verified attendance discount
    "verified_attendance_discount": 0.05,  # 5% for verified attendees
}


class PricingService:
    """
    Service for dynamic pricing and discount optimization.
    
    Integrates:
    - No-show probability for overbooking calculations
    - Host tier influence on pricing power
    - NFT badge holder discounts
    - Verified attendance discounts
    """
    
    def __init__(self):
        self._price_model = None
        self._demand_model = None
    
    def _get_similar_events(
        self,
        db: Session,
        category: Optional[str] = None,
        city: Optional[str] = None,
        capacity: Optional[int] = None,
        day_of_week: Optional[int] = None,
        limit: int = 50
    ) -> pd.DataFrame:
        """Get similar past events for pricing analysis"""
        query = db.query(
            PricingHistory.price,
            PricingHistory.turnout,
            PricingHistory.host_score,
            PricingHistory.city,
            PricingHistory.date,
            PricingHistory.revenue
        )
        
        if city:
            query = query.filter(PricingHistory.city.ilike(f"%{city}%"))
        
        results = query.order_by(PricingHistory.date.desc()).limit(limit).all()
        
        data = []
        for r in results:
            data.append({
                "price": float(r.price) if r.price else 0,
                "turnout": r.turnout or 0,
                "host_score": r.host_score or 50,
                "city": r.city,
                "date": r.date,
                "revenue": float(r.revenue) if r.revenue else 0
            })
        
        return pd.DataFrame(data)
    
    def _estimate_attendance(
        self,
        price: float,
        host_score: float,
        base_demand: float,
        price_elasticity: float = -0.5
    ) -> float:
        """Estimate attendance based on price and other factors"""
        # Simple demand model: demand = base * (1 + elasticity * price_change)
        price_factor = 1 + price_elasticity * (price / 50)  # Normalize around $50
        score_factor = host_score / 50  # Normalize around 50
        
        return max(0, base_demand * price_factor * score_factor)
    
    def optimize_pricing(
        self,
        db: Session,
        event_id: Optional[int] = None,
        category: Optional[str] = None,
        city: Optional[str] = None,
        capacity: int = 50,
        host_score: float = 50.0,
        day_of_week: Optional[int] = None
    ) -> Dict[str, Any]:
        """Suggest optimal ticket price tiers"""
        try:
            # Get similar past events
            historical = self._get_similar_events(
                db, category, city, capacity, day_of_week
            )
            
            if len(historical) < 3:
                # Insufficient data - use defaults
                return {
                    "recommended_tiers": [
                        {"tier": "Budget", "price": 10.0, "expected_attendance": int(capacity * 0.8), "expected_revenue": 10 * capacity * 0.8},
                        {"tier": "Standard", "price": 25.0, "expected_attendance": int(capacity * 0.6), "expected_revenue": 25 * capacity * 0.6},
                        {"tier": "Premium", "price": 50.0, "expected_attendance": int(capacity * 0.4), "expected_revenue": 50 * capacity * 0.4}
                    ],
                    "optimal_price": 25.0,
                    "model": "default",
                    "note": "Insufficient historical data - using default pricing"
                }
            
            # Calculate base metrics
            avg_price = historical["price"].mean()
            avg_turnout = historical["turnout"].mean()
            
            # Price elasticity estimation
            if len(historical) >= 5 and historical["price"].std() > 0:
                # Simple regression for elasticity
                X = historical["price"].values.reshape(-1, 1)
                y = historical["turnout"].values
                model = LinearRegression()
                model.fit(X, y)
                elasticity = model.coef_[0] / avg_turnout if avg_turnout > 0 else -0.5
            else:
                elasticity = -0.5
            
            # Evaluate candidate prices
            candidate_prices = [10, 15, 20, 25, 30, 40, 50, 75, 100]
            evaluations = []
            
            for price in candidate_prices:
                expected_attendance = self._estimate_attendance(
                    price, host_score, avg_turnout, elasticity
                )
                expected_attendance = min(expected_attendance, capacity)
                expected_revenue = price * expected_attendance
                
                evaluations.append({
                    "price": price,
                    "expected_attendance": int(expected_attendance),
                    "expected_revenue": round(expected_revenue, 2)
                })
            
            # Sort by revenue and get top 3
            evaluations.sort(key=lambda x: x["expected_revenue"], reverse=True)
            top_tiers = evaluations[:3]
            
            # Assign tier names
            tier_names = ["Optimal", "Alternative High", "Alternative Low"]
            for i, tier in enumerate(top_tiers):
                tier["tier"] = tier_names[i]
            
            return {
                "recommended_tiers": top_tiers,
                "optimal_price": top_tiers[0]["price"],
                "model": "regression",
                "historical_metrics": {
                    "avg_price": round(avg_price, 2),
                    "avg_turnout": round(avg_turnout, 1),
                    "price_elasticity": round(elasticity, 3)
                },
                "data_points": len(historical)
            }
            
        except Exception as e:
            logger.error(f"Pricing optimization error: {e}")
            return {
                "recommended_tiers": [
                    {"tier": "Standard", "price": 25.0, "expected_attendance": int(capacity * 0.6), "expected_revenue": 25 * capacity * 0.6}
                ],
                "optimal_price": 25.0,
                "model": "fallback",
                "error": str(e)
            }
    
    def suggest_discounts(
        self,
        db: Session,
        event_id: int,
        base_price: float,
        capacity: int = 50,
        current_bookings: int = 0
    ) -> Dict[str, Any]:
        """Recommend discount strategies for audience segments"""
        try:
            # Define segments
            segments = [
                {"name": "Gold Members", "base_conversion": 0.7, "price_sensitivity": 0.3},
                {"name": "Silver Members", "base_conversion": 0.5, "price_sensitivity": 0.5},
                {"name": "Bronze Members", "base_conversion": 0.3, "price_sensitivity": 0.6},
                {"name": "New Users", "base_conversion": 0.2, "price_sensitivity": 0.8},
                {"name": "Nearby Users", "base_conversion": 0.4, "price_sensitivity": 0.5},
                {"name": "Past Attendees", "base_conversion": 0.6, "price_sensitivity": 0.4}
            ]
            
            # Discount levels to evaluate
            discount_levels = [5, 8, 10, 15, 20]
            
            # Calculate potential for each segment
            remaining_capacity = capacity - current_bookings
            suggestions = []
            
            for segment in segments:
                segment_results = []
                
                for discount in discount_levels:
                    # Estimate uplift
                    uplift = segment["base_conversion"] * (1 + discount * segment["price_sensitivity"] / 100)
                    expected_bookings = remaining_capacity * uplift * 0.2  # 20% of remaining reach this segment
                    
                    # Calculate ROI
                    discounted_price = base_price * (1 - discount / 100)
                    revenue_with_discount = expected_bookings * discounted_price
                    revenue_without = expected_bookings * 0.5 * base_price  # Assume 50% would convert anyway
                    discount_cost = expected_bookings * base_price * discount / 100
                    
                    roi = (revenue_with_discount - revenue_without - discount_cost) / max(discount_cost, 1)
                    
                    segment_results.append({
                        "discount_percent": discount,
                        "expected_uplift": round(uplift, 2),
                        "expected_bookings": round(expected_bookings, 1),
                        "roi": round(roi, 2)
                    })
                
                # Find best discount for this segment
                best = max(segment_results, key=lambda x: x["roi"])
                
                suggestions.append({
                    "segment": segment["name"],
                    "recommended_discount": best["discount_percent"],
                    "expected_uplift": best["expected_uplift"],
                    "expected_bookings": best["expected_bookings"],
                    "roi": best["roi"],
                    "all_options": segment_results
                })
            
            # Sort by ROI
            suggestions.sort(key=lambda x: x["roi"], reverse=True)
            
            # Store suggestions in DB
            for sugg in suggestions[:3]:
                discount_record = DiscountSuggestion(
                    event_id=event_id,
                    discount_type="percentage",
                    value_percent=sugg["recommended_discount"],
                    segment=sugg["segment"],
                    expected_uplift=sugg["expected_uplift"],
                    expected_roi=sugg["roi"]
                )
                db.add(discount_record)
            db.commit()
            
            return {
                "event_id": event_id,
                "base_price": base_price,
                "suggestions": suggestions,
                "best_strategy": suggestions[0] if suggestions else None,
                "remaining_capacity": remaining_capacity
            }
            
        except Exception as e:
            logger.error(f"Discount suggestion error: {e}")
            return {
                "event_id": event_id,
                "suggestions": [],
                "error": str(e)
            }

    # ============================================================
    # NEW: NO-SHOW PROBABILITY INTEGRATION
    # ============================================================
    
    def calculate_overbooking_factor(
        self,
        predicted_no_show_rate: float
    ) -> float:
        """
        Calculate overbooking factor based on predicted no-show rate.
        
        Returns multiplier for capacity (e.g., 1.10 = overbook by 10%)
        """
        for threshold, factor in sorted(
            PRICING_CONFIG["no_show_overbooking_thresholds"].items(),
            reverse=True
        ):
            if predicted_no_show_rate >= threshold:
                return factor
        return 1.0  # No overbooking if low no-show rate
    
    def adjust_price_for_no_show_risk(
        self,
        base_price: float,
        predicted_no_show_rate: float
    ) -> Dict[str, Any]:
        """
        Adjust pricing based on predicted no-show rate.
        
        Higher no-show rates may warrant:
        - Slight price reduction (to fill more seats)
        - Or overbooking (to compensate for expected drops)
        """
        overbooking_factor = self.calculate_overbooking_factor(predicted_no_show_rate)
        
        # Price adjustment: higher no-show = slight discount to ensure fills
        if predicted_no_show_rate >= 0.3:
            price_adjustment = 0.95  # 5% discount
        elif predicted_no_show_rate >= 0.2:
            price_adjustment = 0.97  # 3% discount
        else:
            price_adjustment = 1.0  # No adjustment
        
        return {
            "adjusted_price": round(base_price * price_adjustment, 2),
            "overbooking_factor": overbooking_factor,
            "predicted_no_show_rate": predicted_no_show_rate,
            "price_adjustment_percent": round((1 - price_adjustment) * 100, 1)
        }
    
    # ============================================================
    # NEW: HOST TIER PRICING INFLUENCE
    # ============================================================
    
    def get_host_tier_multiplier(
        self,
        db: Session,
        host_id: int
    ) -> Dict[str, Any]:
        """
        Get pricing power multiplier based on host tier.
        
        Premium hosts can command higher prices:
        - Bronze: 1.0x (base)
        - Silver: 1.10x (10% premium)
        - Gold: 1.25x (25% premium)
        """
        host_ml = db.query(UserMLFeatures).filter(
            UserMLFeatures.user_id == host_id
        ).first()
        
        tier = "None"
        if host_ml and host_ml.reward_tier:
            tier = host_ml.reward_tier
        
        multiplier = PRICING_CONFIG["host_tier_multipliers"].get(tier, 1.0)
        
        # Also check host ratings
        avg_rating = db.query(func.avg(HostRating.overall_rating)).filter(
            HostRating.host_id == host_id
        ).scalar() or 3.0
        
        # Rating bonus: 4.5+ gets 5% extra
        rating_bonus = 1.05 if avg_rating >= 4.5 else 1.0
        
        return {
            "tier": tier,
            "tier_multiplier": multiplier,
            "avg_rating": round(float(avg_rating), 2),
            "rating_bonus": rating_bonus,
            "total_multiplier": round(multiplier * rating_bonus, 3)
        }
    
    # ============================================================
    # NEW: USER-SPECIFIC PRICING (NFT + VERIFIED ATTENDANCE)
    # ============================================================
    
    def calculate_user_discounts(
        self,
        db: Session,
        user_id: int,
        base_price: float
    ) -> Dict[str, Any]:
        """
        Calculate user-specific discounts based on:
        - NFT badge level
        - Verified attendance history
        """
        discounts = []
        total_discount = 0.0
        
        # Check NFT badge
        badge = db.query(NFTBadge).filter(
            and_(
                NFTBadge.user_id == user_id,
                NFTBadge.is_active == True
            )
        ).order_by(NFTBadge.level.desc()).first()
        
        if badge:
            nft_discount = PRICING_CONFIG["nft_badge_discounts"].get(
                badge.badge_type, 0.0
            )
            if nft_discount > 0:
                discounts.append({
                    "type": "nft_badge",
                    "reason": f"{badge.badge_type} Badge Holder",
                    "discount_percent": round(nft_discount * 100, 1)
                })
                total_discount += nft_discount
        
        # Check verified attendance history
        user_ml = db.query(UserMLFeatures).filter(
            UserMLFeatures.user_id == user_id
        ).first()
        
        if user_ml and user_ml.attendance_rate_90d and user_ml.attendance_rate_90d >= 0.9:
            verified_discount = PRICING_CONFIG["verified_attendance_discount"]
            discounts.append({
                "type": "verified_attendance",
                "reason": "Verified Attendance (90%+ rate)",
                "discount_percent": round(verified_discount * 100, 1)
            })
            total_discount += verified_discount
        
        # Calculate final price
        final_price = base_price * (1 - total_discount)
        
        return {
            "base_price": base_price,
            "discounts": discounts,
            "total_discount_percent": round(total_discount * 100, 1),
            "final_price": round(final_price, 2)
        }
    
    # ============================================================
    # NEW: ENHANCED PRICING OPTIMIZATION
    # ============================================================
    
    def optimize_pricing_enhanced(
        self,
        db: Session,
        event_id: int,
        host_id: int,
        category: Optional[str] = None,
        city: Optional[str] = None,
        capacity: int = 50,
        day_of_week: Optional[int] = None,
        predicted_no_show_rate: float = 0.15
    ) -> Dict[str, Any]:
        """
        Enhanced pricing optimization with all factors:
        - Base pricing from historical data
        - Host tier multiplier
        - No-show rate adjustment
        - Recommended user discounts
        """
        # Get base optimized price
        base_result = self.optimize_pricing(
            db=db,
            category=category,
            city=city,
            capacity=capacity,
            day_of_week=day_of_week
        )
        
        base_price = base_result.get("optimal_price", PRICING_CONFIG["default_price"])
        
        # Apply host tier multiplier
        host_multiplier = self.get_host_tier_multiplier(db, host_id)
        price_with_host = base_price * host_multiplier["total_multiplier"]
        
        # Adjust for no-show risk
        no_show_adjustment = self.adjust_price_for_no_show_risk(
            price_with_host, predicted_no_show_rate
        )
        
        # Final recommended price
        final_price = no_show_adjustment["adjusted_price"]
        
        # Clamp to min/max
        final_price = max(
            PRICING_CONFIG["min_price"],
            min(final_price, PRICING_CONFIG["max_price"])
        )
        
        # Store enhanced pricing in DB
        pricing_record = PricingHistory(
            event_id=event_id,
            price=final_price,
            demand_score=base_result.get("historical_metrics", {}).get("avg_turnout", 0) / capacity,
            category=category,
            city=city,
            capacity=capacity,
            day_of_week=day_of_week
        )
        db.add(pricing_record)
        db.commit()
        
        return {
            "event_id": event_id,
            "recommended_price": round(final_price, 2),
            "pricing_breakdown": {
                "base_price": round(base_price, 2),
                "host_tier": host_multiplier["tier"],
                "host_multiplier": host_multiplier["total_multiplier"],
                "price_after_host": round(price_with_host, 2),
                "no_show_adjustment": no_show_adjustment,
                "final_price": round(final_price, 2)
            },
            "overbooking_recommendation": {
                "base_capacity": capacity,
                "overbooking_factor": no_show_adjustment["overbooking_factor"],
                "adjusted_capacity": int(capacity * no_show_adjustment["overbooking_factor"]),
                "reason": f"Predicted {round(predicted_no_show_rate * 100, 1)}% no-show rate"
            },
            "nft_discount_tiers": PRICING_CONFIG["nft_badge_discounts"],
            "model": "enhanced",
            "base_analysis": base_result
        }


# Singleton instance
pricing_service = PricingService()
