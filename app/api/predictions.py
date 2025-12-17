"""
Prediction API endpoints.
Handles attendance forecasting and trend prediction using Prophet.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import datetime
import logging

from app.database import get_db
from app.services.prediction_service import PredictionService
from app.schemas.schemas import (
    AttendancePredictionRequest,
    AttendancePredictionResponse,
    TrendPredictionResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/predict", tags=["Predictions"])


@router.post(
    "/attendance",
    response_model=AttendancePredictionResponse,
    summary="Predict Event Attendance",
    description="""
    Predict attendance for a specific event.
    
    **Models used (v1):**
    - Prophet (time-series forecasting)
    - Scikit-learn regression (no-show/turnout prediction)
    
    **Factors considered:**
    - Historical attendance patterns
    - Day of week / time of day
    - Category popularity
    - Host rating
    - Weather (if available)
    - Competing events
    
    **Output:**
    - Predicted attendance (number)
    - Confidence interval (± range)
    - MAE/RMSE metrics (not 95% accuracy requirement)
    """
)
async def predict_attendance(
    request: AttendancePredictionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Predict attendance for an event."""
    try:
        result = await PredictionService.predict_attendance(
            db=db,
            event_id=request.event_id,
            event_date=request.event_date,
            category=request.category,
            location=request.location,
            capacity=request.capacity,
            host_id=request.host_id
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Attendance prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/trends",
    response_model=TrendPredictionResponse,
    summary="Predict Best Time/Day Trends",
    description="""
    Get best day/time to host for a hobby/location.
    
    **Output:**
    - Ranked times/days by expected attendance
    - Historical average attendance
    - Optional confidence score
    
    Useful for event organizers planning optimal scheduling.
    """
)
async def predict_trends(
    category: Optional[str] = Query(None, description="Hobby/category"),
    location: Optional[str] = Query(None, description="Location/city"),
    lat: Optional[float] = Query(None, description="Latitude"),
    lon: Optional[float] = Query(None, description="Longitude"),
    db: AsyncSession = Depends(get_db)
):
    """Get trend predictions for best hosting times."""
    try:
        result = await PredictionService.predict_trends(
            db=db,
            category=category,
            location=location,
            lat=lat,
            lon=lon
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Trend prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/demand/{category}",
    summary="Predict Category Demand",
    description="Predict demand for a specific category over time."
)
async def predict_demand(
    category: str,
    days_ahead: int = Query(30, ge=1, le=90, description="Days to forecast"),
    location: Optional[str] = Query(None, description="Location filter"),
    db: AsyncSession = Depends(get_db)
):
    """Predict demand for a category."""
    try:
        result = await PredictionService.predict_demand(
            db=db,
            category=category,
            days_ahead=days_ahead,
            location=location
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Demand prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/no-show-rate",
    summary="Predict No-Show Rate",
    description="Predict no-show rate for an event based on historical patterns."
)
async def predict_no_show_rate(
    event_id: Optional[str] = Query(None, description="Event ID"),
    category: Optional[str] = Query(None, description="Category"),
    is_free: bool = Query(False, description="Is event free?"),
    days_until_event: int = Query(7, ge=0, le=365, description="Days until event"),
    db: AsyncSession = Depends(get_db)
):
    """Predict no-show rate."""
    try:
        result = await PredictionService.predict_no_show_rate(
            db=db,
            event_id=event_id,
            category=category,
            is_free=is_free,
            days_until_event=days_until_event
        )
        
        return result
        
    except Exception as e:
        logger.error(f"No-show prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
