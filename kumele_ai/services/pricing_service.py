"""
Pricing Service - Handles dynamic pricing and discount optimization
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
    RewardCoupon, User, HostRating
)

logger = logging.getLogger(__name__)


class PricingService:
    """Service for dynamic pricing and discount optimization"""
    
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


# Singleton instance
pricing_service = PricingService()
