"""
Predictions Router - Attendance prediction and trends endpoints
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session

from kumele_ai.dependencies import get_db
from kumele_ai.services.forecast_service import forecast_service

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
