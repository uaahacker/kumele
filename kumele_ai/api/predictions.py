"""
Predictions Router - Attendance prediction and no-show forecasting endpoints

Provides:
- POST /attendance: Predict attendance for an event
- GET /trends: Get attendance trends
- GET /noshow/{event_id}: Predict no-show probability for an event
- POST /noshow/user: Predict no-show probability for a specific user
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from kumele_ai.dependencies import get_db
from kumele_ai.services.forecast_service import forecast_service
from kumele_ai.services.no_show_service import no_show_service
from kumele_ai.db.models import Event, User, UserEvent

router = APIRouter()


class AttendancePredictionRequest(BaseModel):
    hobby: str
    location: str
    date: datetime
    time: Optional[datetime] = None
    is_paid: bool = False
    host_experience: int = 0
    host_rating: float = 3.0
    capacity: int = 20


class NoShowPredictionResponse(BaseModel):
    """Response model for no-show prediction"""
    event_id: int
    user_id: Optional[int] = None
    no_show_probability: float = Field(..., ge=0.0, le=1.0)
    risk_level: str  # "low", "medium", "high", "critical"
    confidence: float = Field(..., ge=0.0, le=1.0)
    
    # Feature breakdown
    feature_contributions: Optional[dict] = None
    top_risk_factors: Optional[List[str]] = None
    
    # Recommendations
    recommended_actions: Optional[List[str]] = None


class UserNoShowRequest(BaseModel):
    """Request model for user-specific no-show prediction"""
    event_id: int
    user_id: int


@router.post("/attendance")
async def predict_attendance(
    request: AttendancePredictionRequest,
    db: Session = Depends(get_db)
):
    """
    Predict attendance for an event.
    
    Uses Prophet + sklearn models (NOT TFRS for v1).
    
    Inputs:
    - hobby: Event hobby/category
    - location: City/area
    - date & time: When the event will be held
    - is_paid: Free or paid event
    - host_experience: Number of events hosted
    - host_rating: Host's rating (0-5)
    - capacity: Maximum attendees
    
    Outputs:
    - predicted_attendance: Expected number of attendees
    - confidence_interval: {lower, upper} bounds
    - confidence_band: e.g., "±20%"
    """
    result = forecast_service.predict_attendance(
        db=db,
        hobby=request.hobby,
        location=request.location,
        date=request.date,
        time=request.time,
        is_paid=request.is_paid,
        host_experience=request.host_experience,
        host_rating=request.host_rating,
        capacity=request.capacity
    )
    
    return result


@router.get("/trends")
async def get_trends(
    hobby: Optional[str] = Query(None, description="Filter by hobby"),
    location: Optional[str] = Query(None, description="Filter by location"),
    db: Session = Depends(get_db)
):
    """
    Get attendance trends for events.
    
    Returns:
    - ranked_times: Best days/times for events
    - historical_average: Average attendance
    - confidence_score: Reliability of predictions
    """
    result = forecast_service.get_trends(
        db=db,
        hobby=hobby,
        location=location
    )
    
    return result


# ============================================================
# NO-SHOW PREDICTION ENDPOINTS
# ============================================================

@router.get("/noshow/{event_id}", response_model=NoShowPredictionResponse)
async def predict_event_noshow(
    event_id: int,
    db: Session = Depends(get_db)
):
    """
    Predict aggregate no-show probability for an event.
    
    Uses interpretable logistic regression model with features:
    - Distance from event (km)
    - Hours until event
    - User's past no-show rate
    - Payment status
    - Host reliability score
    - Day of week patterns
    - Weather conditions (if available)
    
    Returns:
    - no_show_probability: 0.0-1.0 probability
    - risk_level: "low" (<10%), "medium" (10-25%), "high" (25-50%), "critical" (>50%)
    - feature_contributions: Breakdown by feature
    - recommended_actions: Mitigation strategies
    """
    # Get event
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Get all registered users
    registrations = db.query(UserEvent).filter(
        UserEvent.event_id == event_id
    ).all()
    
    if not registrations:
        return NoShowPredictionResponse(
            event_id=event_id,
            no_show_probability=0.0,
            risk_level="low",
            confidence=0.5,
            recommended_actions=["No registrations yet"]
        )
    
    # Predict for each user and aggregate
    predictions = []
    all_risk_factors = []
    
    for reg in registrations:
        result = no_show_service.predict(
            db=db,
            user_id=reg.user_id,
            event_id=event_id
        )
        predictions.append(result["probability"])
        if result.get("risk_factors"):
            all_risk_factors.extend(result["risk_factors"])
    
    # Aggregate metrics
    avg_probability = sum(predictions) / len(predictions)
    
    # Risk level
    if avg_probability < 0.10:
        risk_level = "low"
    elif avg_probability < 0.25:
        risk_level = "medium"
    elif avg_probability < 0.50:
        risk_level = "high"
    else:
        risk_level = "critical"
    
    # Top risk factors (most common)
    from collections import Counter
    factor_counts = Counter(all_risk_factors)
    top_factors = [f[0] for f in factor_counts.most_common(5)]
    
    # Generate recommendations
    recommendations = _generate_noshow_recommendations(avg_probability, top_factors)
    
    return NoShowPredictionResponse(
        event_id=event_id,
        no_show_probability=round(avg_probability, 4),
        risk_level=risk_level,
        confidence=min(len(predictions) / 10, 1.0),  # More data = higher confidence
        top_risk_factors=top_factors,
        recommended_actions=recommendations
    )


@router.post("/noshow/user", response_model=NoShowPredictionResponse)
async def predict_user_noshow(
    request: UserNoShowRequest,
    db: Session = Depends(get_db)
):
    """
    Predict no-show probability for a specific user on a specific event.
    
    Uses interpretable logistic regression with user-specific features:
    - User's historical no-show rate
    - Distance from event
    - Payment behavior (timeout rate)
    - NFT badge status (trust indicator)
    - Time since RSVP
    
    Returns detailed feature contributions for explainability.
    """
    # Validate event and user
    event = db.query(Event).filter(Event.id == request.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    user = db.query(User).filter(User.id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get prediction
    result = no_show_service.predict(
        db=db,
        user_id=request.user_id,
        event_id=request.event_id
    )
    
    probability = result["probability"]
    
    # Risk level
    if probability < 0.10:
        risk_level = "low"
    elif probability < 0.25:
        risk_level = "medium"
    elif probability < 0.50:
        risk_level = "high"
    else:
        risk_level = "critical"
    
    # Generate recommendations
    recommendations = _generate_noshow_recommendations(
        probability, 
        result.get("risk_factors", [])
    )
    
    return NoShowPredictionResponse(
        event_id=request.event_id,
        user_id=request.user_id,
        no_show_probability=round(probability, 4),
        risk_level=risk_level,
        confidence=result.get("confidence", 0.7),
        feature_contributions=result.get("features"),
        top_risk_factors=result.get("risk_factors"),
        recommended_actions=recommendations
    )


def _generate_noshow_recommendations(probability: float, risk_factors: List[str]) -> List[str]:
    """Generate actionable recommendations based on no-show prediction"""
    recommendations = []
    
    if probability >= 0.50:
        recommendations.append("Consider overbooking by 20% to compensate for no-shows")
        recommendations.append("Send multiple reminders closer to event date")
    elif probability >= 0.25:
        recommendations.append("Send a reminder 24 hours before the event")
        recommendations.append("Consider requiring deposits for paid events")
    elif probability >= 0.10:
        recommendations.append("Standard reminder 1 day before recommended")
    else:
        recommendations.append("Low no-show risk - no special actions needed")
    
    # Factor-specific recommendations
    if "high_distance" in risk_factors:
        recommendations.append("Offer virtual attendance option for distant users")
    
    if "payment_timeout" in risk_factors:
        recommendations.append("Require immediate payment to confirm RSVP")
    
    if "short_notice_rsvp" in risk_factors:
        recommendations.append("Monitor last-minute RSVPs more closely")
    
    if "low_host_rating" in risk_factors:
        recommendations.append("Improve host profile and past event reviews")
    
    return recommendations
