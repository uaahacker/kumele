"""
No-Show Prediction Service - Behavioral Forecasting

Estimates the probability that a user will NOT attend an event after RSVP.

This is NOT moderation. This is behavioral forecasting used for:
- Pricing Optimization
- Discount Suggestion Engine
- Attendance Forecasting
- Matching/Ranking fairness

Output: no_show_probability ∈ [0.0, 1.0], confidence ∈ [0.0, 1.0]
"""
import logging
import math
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
import numpy as np

from kumele_ai.db.models import (
    User, Event, UserEvent, UserAttendanceProfile, 
    NoShowPrediction, EventCategoryNoShowStats, HostRating, Hobby
)

logger = logging.getLogger(__name__)

# Model version for tracking
MODEL_VERSION = "1.0.0-logistic"

# Feature weights (interpretable logistic regression coefficients)
# Positive weight = increases no-show probability
# Negative weight = decreases no-show probability
FEATURE_WEIGHTS = {
    # User behavioral signals
    "user_no_show_rate": 2.5,           # Historical no-show rate is strongest predictor
    "user_late_cancellation_rate": 1.2,
    "user_payment_failure_rate": 0.8,
    "user_is_new": 0.4,                  # New users have slightly higher no-show
    "user_last_minute_rsvp_rate": 0.6,
    
    # Distance signals
    "distance_above_typical": 0.5,       # Farther than usual
    "distance_normalized": 0.3,          # Raw distance effect
    
    # Event signals
    "event_is_free": 0.7,                # Free events have higher no-show
    "event_is_pay_in_person": 0.3,       # Pay-in-person slightly higher
    "event_weekday_evening": 0.4,        # Weekday evenings have higher no-show
    "event_category_base_rate": 1.0,     # Category-specific base rate
    
    # Host signals
    "host_low_reliability": 0.5,         # Unreliable hosts have higher attendee no-show
    
    # Timing signals
    "hours_until_event_short": 0.3,      # Very short notice RSVPs
    "hours_until_event_long": -0.2,      # Long advance RSVPs are more committed
    
    # Payment signals
    "payment_completed_quickly": -0.6,   # Quick payment = commitment
    "payment_not_completed": 0.4,        # No payment yet for paid event
}

INTERCEPT = -1.5  # Base log-odds (corresponds to ~18% base no-show rate)


class NoShowService:
    """
    Service for predicting no-show probability.
    
    Uses logistic regression with interpretable features.
    All predictions are logged for audit trail and model improvement.
    """
    
    def predict(
        self,
        db: Session,
        user_id: int,
        event_id: int,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Predict no-show probability for a user-event pair.
        
        Args:
            db: Database session
            user_id: User ID
            event_id: Event ID
            context: Additional context:
                - price_mode: 'paid', 'free', 'pay_in_person'
                - distance_km: Distance from user to event
                - rsvp_timestamp: When RSVP was made
                - event_start_timestamp: Event start time
                - payment_completed: Whether payment is done
                - payment_time_minutes: Minutes to complete payment
                
        Returns:
            {
                "no_show_probability": 0.27,
                "confidence": 0.74,
                "features": {...},  # For explainability
                "model_version": "1.0.0-logistic"
            }
        """
        try:
            # Extract features
            features = self._extract_features(db, user_id, event_id, context)
            
            # Calculate prediction
            no_show_prob, confidence = self._calculate_prediction(features)
            
            # Generate top risk factors based on features
            top_risk_factors = self._get_top_risk_factors(features)
            
            # Log prediction for audit trail
            self._log_prediction(
                db=db,
                user_id=user_id,
                event_id=event_id,
                no_show_probability=no_show_prob,
                confidence=confidence,
                features=features,
                context=context
            )
            
            return {
                "no_show_probability": round(no_show_prob, 4),
                "confidence": round(confidence, 4),
                "expected_show_probability": round(1 - no_show_prob, 4),
                "features": features,
                "top_risk_factors": top_risk_factors,
                "model_version": MODEL_VERSION
            }
            
        except Exception as e:
            logger.error(f"Error predicting no-show: {e}")
            # Return conservative estimate on error
            return {
                "no_show_probability": 0.25,
                "confidence": 0.3,
                "expected_show_probability": 0.75,
                "features": {},
                "top_risk_factors": [],
                "model_version": MODEL_VERSION,
                "error": str(e)
            }
    
    def _extract_features(
        self,
        db: Session,
        user_id: int,
        event_id: int,
        context: Dict[str, Any]
    ) -> Dict[str, float]:
        """Extract all features for the prediction model."""
        features = {}
        
        # 1. User Behavioral Signals
        user_profile = self._get_user_attendance_profile(db, user_id)
        features["user_no_show_rate"] = user_profile.get("no_show_rate", 0.2)
        features["user_check_in_rate"] = user_profile.get("check_in_rate", 0.8)
        features["user_is_new"] = 1.0 if user_profile.get("total_rsvps", 0) < 3 else 0.0
        features["user_late_cancellation_rate"] = user_profile.get("late_cancellation_rate", 0.0)
        features["user_payment_failure_rate"] = user_profile.get("payment_failure_rate", 0.0)
        features["user_last_minute_rsvp_rate"] = user_profile.get("last_minute_rsvp_rate", 0.0)
        features["user_avg_distance_km"] = user_profile.get("avg_distance_km", 10.0)
        
        # 2. Event Signals
        event = db.query(Event).filter(Event.id == event_id).first()
        if event:
            features["event_is_free"] = 1.0 if not event.is_paid else 0.0
            features["event_is_paid"] = 1.0 if event.is_paid else 0.0
            
            # Price mode from context
            price_mode = context.get("price_mode", "free")
            features["event_is_pay_in_person"] = 1.0 if price_mode == "pay_in_person" else 0.0
            
            # Time-based signals
            if event.event_date:
                day_of_week = event.event_date.weekday()
                hour = event.event_date.hour if hasattr(event.event_date, 'hour') else 19
                features["event_weekday_evening"] = 1.0 if (day_of_week < 5 and 17 <= hour <= 21) else 0.0
                features["event_weekend"] = 1.0 if day_of_week >= 5 else 0.0
            
            # Category base rate
            category_rate = self._get_category_no_show_rate(db, event, price_mode)
            features["event_category_base_rate"] = category_rate
        
        # 3. Distance Signals
        distance_km = context.get("distance_km", 5.0)
        features["distance_km"] = distance_km
        features["distance_normalized"] = min(distance_km / 50.0, 1.0)  # Normalize to 50km max
        
        avg_distance = user_profile.get("avg_distance_km", 10.0)
        if avg_distance and avg_distance > 0:
            features["distance_above_typical"] = max(0, (distance_km - avg_distance) / avg_distance)
        else:
            features["distance_above_typical"] = 0.0
        
        # 4. Host Signals
        if event and event.host_id:
            host_reliability = self._get_host_reliability(db, event.host_id)
            features["host_reliability_score"] = host_reliability
            features["host_low_reliability"] = 1.0 if host_reliability < 0.7 else 0.0
        
        # 5. Timing Signals
        rsvp_timestamp = context.get("rsvp_timestamp")
        event_start = context.get("event_start_timestamp")
        
        if rsvp_timestamp and event_start:
            # Parse timestamps if strings
            if isinstance(rsvp_timestamp, str):
                rsvp_timestamp = datetime.fromisoformat(rsvp_timestamp.replace("Z", "+00:00"))
            if isinstance(event_start, str):
                event_start = datetime.fromisoformat(event_start.replace("Z", "+00:00"))
            
            hours_until = (event_start - rsvp_timestamp).total_seconds() / 3600
            features["hours_until_event"] = hours_until
            features["hours_until_event_short"] = 1.0 if hours_until < 24 else 0.0
            features["hours_until_event_long"] = 1.0 if hours_until > 168 else 0.0  # > 1 week
        
        # 6. Payment Signals
        payment_completed = context.get("payment_completed", False)
        payment_time = context.get("payment_time_minutes")
        
        if context.get("price_mode") == "paid":
            features["payment_completed"] = 1.0 if payment_completed else 0.0
            features["payment_not_completed"] = 0.0 if payment_completed else 1.0
            features["payment_completed_quickly"] = 1.0 if payment_completed and payment_time and payment_time < 10 else 0.0
        else:
            features["payment_completed"] = 0.0
            features["payment_not_completed"] = 0.0
            features["payment_completed_quickly"] = 0.0
        
        return features
    
    def _calculate_prediction(
        self,
        features: Dict[str, float]
    ) -> Tuple[float, float]:
        """
        Calculate no-show probability using logistic regression.
        
        Returns: (no_show_probability, confidence)
        """
        # Calculate log-odds
        log_odds = INTERCEPT
        
        for feature_name, weight in FEATURE_WEIGHTS.items():
            if feature_name in features:
                log_odds += weight * features[feature_name]
        
        # Convert to probability using sigmoid
        no_show_prob = 1.0 / (1.0 + math.exp(-log_odds))
        
        # Calculate confidence based on:
        # - Amount of historical data for user
        # - Distance from decision boundary (0.5)
        # - Feature completeness
        
        user_data_confidence = min(1.0, features.get("user_check_in_rate", 0) + 
                                   (1 - features.get("user_is_new", 1)) * 0.5)
        
        # Distance from 0.5 (more extreme = more confident in direction)
        boundary_confidence = abs(no_show_prob - 0.5) * 2
        
        # Feature completeness
        expected_features = len(FEATURE_WEIGHTS)
        actual_features = sum(1 for k in FEATURE_WEIGHTS if k in features and features[k] != 0)
        completeness = actual_features / expected_features
        
        confidence = (user_data_confidence * 0.4 + 
                     boundary_confidence * 0.3 + 
                     completeness * 0.3)
        
        return no_show_prob, min(max(confidence, 0.1), 0.95)
    
    def _get_top_risk_factors(self, features: Dict[str, float]) -> List[str]:
        """
        Get top risk factors based on feature values.
        Returns human-readable risk factor names.
        """
        risk_factors = []
        
        # Map features to human-readable risk factors
        feature_to_risk = {
            "user_no_show_rate": ("high_no_show_history", 0.3),
            "user_is_new": ("new_user", 0.5),
            "user_late_cancellation_rate": ("late_cancellation_history", 0.2),
            "user_payment_failure_rate": ("payment_timeout", 0.1),
            "distance_above_typical": ("high_distance", 0.3),
            "event_is_free": ("free_event", 0.5),
            "event_weekday_evening": ("weekday_evening", 0.5),
            "host_low_reliability": ("low_host_rating", 0.5),
            "hours_until_event_short": ("short_notice_rsvp", 0.5),
            "payment_not_completed": ("payment_pending", 0.5),
        }
        
        for feature_name, (risk_name, threshold) in feature_to_risk.items():
            if features.get(feature_name, 0) >= threshold:
                risk_factors.append(risk_name)
        
        return risk_factors[:5]  # Return top 5 risk factors
    
    def _get_user_attendance_profile(
        self,
        db: Session,
        user_id: int
    ) -> Dict[str, float]:
        """Get or compute user attendance profile."""
        profile = db.query(UserAttendanceProfile).filter(
            UserAttendanceProfile.user_id == user_id
        ).first()
        
        if profile:
            late_cancel_rate = (profile.late_cancellations / profile.total_rsvps 
                               if profile.total_rsvps > 0 else 0.0)
            payment_fail_rate = (profile.failed_payments / max(profile.total_rsvps, 1))
            last_min_rate = (profile.last_minute_rsvp_count / max(profile.total_rsvps, 1))
            
            return {
                "total_rsvps": profile.total_rsvps,
                "total_check_ins": profile.total_check_ins,
                "no_show_rate": profile.no_show_rate or 0.2,
                "check_in_rate": profile.check_in_rate or 0.8,
                "late_cancellation_rate": late_cancel_rate,
                "payment_failure_rate": payment_fail_rate,
                "last_minute_rsvp_rate": last_min_rate,
                "avg_distance_km": profile.avg_distance_km or 10.0
            }
        
        # New user - compute from user_events if available
        events = db.query(UserEvent).filter(UserEvent.user_id == user_id).all()
        
        if not events:
            return {
                "total_rsvps": 0,
                "total_check_ins": 0,
                "no_show_rate": 0.2,  # Default for new users
                "check_in_rate": 0.8,
                "late_cancellation_rate": 0.0,
                "payment_failure_rate": 0.0,
                "last_minute_rsvp_rate": 0.0,
                "avg_distance_km": 10.0
            }
        
        total = len(events)
        attended = sum(1 for e in events if e.checked_in)
        no_shows = sum(1 for e in events if e.rsvp_status == "no_show")
        
        return {
            "total_rsvps": total,
            "total_check_ins": attended,
            "no_show_rate": no_shows / total if total > 0 else 0.2,
            "check_in_rate": attended / total if total > 0 else 0.8,
            "late_cancellation_rate": 0.0,
            "payment_failure_rate": 0.0,
            "last_minute_rsvp_rate": 0.0,
            "avg_distance_km": 10.0
        }
    
    def _get_category_no_show_rate(
        self,
        db: Session,
        event: Event,
        price_mode: str
    ) -> float:
        """Get historical no-show rate for event category."""
        category = None
        if event.hobby_id:
            hobby = db.query(Hobby).filter(Hobby.id == event.hobby_id).first()
            if hobby:
                category = hobby.category
        
        if not category:
            return 0.2  # Default
        
        stats = db.query(EventCategoryNoShowStats).filter(
            and_(
                EventCategoryNoShowStats.category == category,
                EventCategoryNoShowStats.price_mode == price_mode
            )
        ).first()
        
        if stats and stats.avg_no_show_rate is not None:
            return stats.avg_no_show_rate
        
        return 0.2  # Default
    
    def _get_host_reliability(self, db: Session, host_id: int) -> float:
        """Get host reliability score."""
        host_rating = db.query(HostRating).filter(
            HostRating.host_id == host_id
        ).first()
        
        if host_rating and host_rating.overall_score:
            return host_rating.overall_score / 5.0  # Normalize to 0-1
        
        return 0.8  # Default for new hosts
    
    def _log_prediction(
        self,
        db: Session,
        user_id: int,
        event_id: int,
        no_show_probability: float,
        confidence: float,
        features: Dict[str, float],
        context: Dict[str, Any]
    ) -> None:
        """Log prediction for audit trail."""
        try:
            # Parse timestamps
            rsvp_ts = context.get("rsvp_timestamp")
            event_ts = context.get("event_start_timestamp")
            
            if isinstance(rsvp_ts, str):
                rsvp_ts = datetime.fromisoformat(rsvp_ts.replace("Z", "+00:00"))
            if isinstance(event_ts, str):
                event_ts = datetime.fromisoformat(event_ts.replace("Z", "+00:00"))
            
            hours_until = None
            if rsvp_ts and event_ts:
                hours_until = (event_ts - rsvp_ts).total_seconds() / 3600
            
            prediction = NoShowPrediction(
                user_id=user_id,
                event_id=event_id,
                no_show_probability=no_show_probability,
                confidence=confidence,
                features=features,
                price_mode=context.get("price_mode"),
                distance_km=context.get("distance_km"),
                rsvp_timestamp=rsvp_ts,
                event_start_timestamp=event_ts,
                hours_until_event=hours_until,
                model_version=MODEL_VERSION
            )
            db.add(prediction)
            db.commit()
        except Exception as e:
            logger.error(f"Error logging prediction: {e}")
            db.rollback()
    
    def record_outcome(
        self,
        db: Session,
        user_id: int,
        event_id: int,
        outcome: str  # 'attended', 'no_show', 'cancelled'
    ) -> Dict[str, Any]:
        """
        Record actual outcome for a prediction.
        Used for model training and improvement.
        """
        try:
            # Find the latest prediction for this user-event pair
            prediction = db.query(NoShowPrediction).filter(
                and_(
                    NoShowPrediction.user_id == user_id,
                    NoShowPrediction.event_id == event_id
                )
            ).order_by(NoShowPrediction.created_at.desc()).first()
            
            if prediction:
                prediction.actual_outcome = outcome
                prediction.outcome_recorded_at = datetime.utcnow()
                db.commit()
                return {"success": True, "prediction_id": prediction.id}
            
            return {"success": False, "error": "No prediction found"}
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error recording outcome: {e}")
            return {"success": False, "error": str(e)}
    
    def update_user_profile(
        self,
        db: Session,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Update user attendance profile based on historical data.
        Should be called periodically or after events.
        """
        try:
            events = db.query(UserEvent).filter(UserEvent.user_id == user_id).all()
            
            if not events:
                return {"success": False, "error": "No events found"}
            
            total_rsvps = len(events)
            total_check_ins = sum(1 for e in events if e.checked_in)
            total_no_shows = sum(1 for e in events if e.rsvp_status == "no_show")
            
            # Get or create profile
            profile = db.query(UserAttendanceProfile).filter(
                UserAttendanceProfile.user_id == user_id
            ).first()
            
            if not profile:
                profile = UserAttendanceProfile(user_id=user_id)
                db.add(profile)
            
            profile.total_rsvps = total_rsvps
            profile.total_check_ins = total_check_ins
            profile.total_no_shows = total_no_shows
            profile.check_in_rate = total_check_ins / total_rsvps if total_rsvps > 0 else 0.8
            profile.no_show_rate = total_no_shows / total_rsvps if total_rsvps > 0 else 0.2
            profile.last_updated = datetime.utcnow()
            
            db.commit()
            
            return {"success": True, "profile_id": profile.id}
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating user profile: {e}")
            return {"success": False, "error": str(e)}
    
    def batch_predict(
        self,
        db: Session,
        event_id: int,
        user_ids: List[int],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Batch predict no-show probabilities for multiple users.
        Used for attendance forecasting.
        """
        predictions = []
        total_expected_attendance = 0.0
        
        for user_id in user_ids:
            result = self.predict(db, user_id, event_id, context)
            predictions.append({
                "user_id": user_id,
                "no_show_probability": result["no_show_probability"],
                "confidence": result["confidence"]
            })
            total_expected_attendance += result["expected_show_probability"]
        
        return {
            "event_id": event_id,
            "total_rsvps": len(user_ids),
            "expected_attendance": round(total_expected_attendance, 1),
            "avg_no_show_probability": round(
                sum(p["no_show_probability"] for p in predictions) / len(predictions), 4
            ) if predictions else 0.0,
            "predictions": predictions
        }


# Singleton instance
no_show_service = NoShowService()
