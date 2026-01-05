"""
Engagement / Retention Risk API - GET /engagement/retention-risk

Predicts user churn probability and provides retention risk assessment.

Endpoint:
    GET /engagement/retention-risk?user_id=123

Features Used:
    - days_since_last_login
    - days_since_last_event
    - events_attended_30d, 60d, 90d
    - messages_sent_30d
    - blog_interactions_30d
    - event_interactions_30d
    - notification_open_ratio
    - reward_tier
    - has_purchase

Response:
{
    "user_id": 123,
    "churn_probability": 0.65,
    "risk_band": "medium",
    "recommended_action": "Send targeted re-engagement campaign within 48 hours",
    "features": {...},
    "feature_importance": {...},
    "model_name": "RandomForestClassifier",
    "prediction_date": "2024-01-15T10:30:00Z",
    "valid_until": "2024-01-16T10:30:00Z"
}
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from app.database import get_db
from app.services.retention_service import RetentionRiskService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/engagement", tags=["Engagement & Retention"])


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class RetentionRiskResponse(BaseModel):
    """Response for retention risk prediction."""
    user_id: int
    churn_probability: float = Field(..., ge=0, le=1, description="Probability of churn (0-1)")
    risk_band: str = Field(..., description="Risk level: low | medium | high")
    recommended_action: str = Field(..., description="Suggested retention action")
    features: Dict[str, Any] = Field(..., description="Features used for prediction")
    feature_importance: Dict[str, float] = Field(..., description="Feature importance weights")
    model_name: str = Field(..., description="Model used for prediction")
    prediction_date: str = Field(..., description="When prediction was made")
    valid_until: str = Field(..., description="Prediction validity expiry")
    prediction_id: Optional[str] = Field(None, description="Database record ID")
    cached: Optional[bool] = Field(False, description="Whether result was cached")
    processing_time_ms: Optional[float] = Field(None, description="Processing time in ms")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 123,
                "churn_probability": 0.65,
                "risk_band": "medium",
                "recommended_action": "Send targeted re-engagement campaign within 48 hours",
                "features": {
                    "days_since_last_login": 15,
                    "days_since_last_event": 45,
                    "events_attended_30d": 0,
                    "events_attended_60d": 1,
                    "events_attended_90d": 2,
                    "messages_sent_30d": 3,
                    "blog_interactions_30d": 0,
                    "event_interactions_30d": 1,
                    "notification_open_ratio": 0.35,
                    "reward_tier": 1,
                    "has_purchase": 0
                },
                "feature_importance": {
                    "days_since_last_login": 0.20,
                    "days_since_last_event": 0.18,
                    "events_attended_30d": 0.12,
                    "events_attended_60d": 0.05,
                    "events_attended_90d": 0.08,
                    "messages_sent_30d": 0.08,
                    "blog_interactions_30d": 0.05,
                    "event_interactions_30d": 0.07,
                    "notification_open_ratio": 0.07,
                    "reward_tier": 0.05,
                    "has_purchase": 0.05
                },
                "model_name": "RuleBasedChurnModel",
                "prediction_date": "2024-01-15T10:30:00",
                "valid_until": "2024-01-16T10:30:00",
                "prediction_id": "550e8400-e29b-41d4-a716-446655440000",
                "cached": False,
                "processing_time_ms": 45.2
            }
        }


class BatchRetentionRequest(BaseModel):
    """Request for batch retention risk predictions."""
    user_ids: List[int] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of user IDs (max 100)"
    )


class HighRiskUserResponse(BaseModel):
    """Response for high risk user."""
    user_id: int
    churn_probability: float
    risk_band: str
    recommended_action: str
    prediction_date: str


class RetentionStatsResponse(BaseModel):
    """Response for retention statistics."""
    total_users_analyzed: int
    risk_distribution: Dict[str, int]
    risk_percentages: Dict[str, float]
    average_churn_probability: float


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get(
    "/retention-risk",
    response_model=RetentionRiskResponse,
    summary="Get user retention risk",
    description="""
Predict churn probability and retention risk for a user.

**Features Analyzed:**
- Login activity (days_since_last_login)
- Event attendance patterns (30d, 60d, 90d)
- Engagement metrics (messages, notifications, blog interactions)
- Loyalty indicators (reward_tier, purchase history)

**Risk Bands:**
- **low**: churn_probability < 0.4 (continue standard engagement)
- **medium**: 0.4 ≤ churn_probability < 0.7 (send re-engagement campaign)
- **high**: churn_probability ≥ 0.7 (immediate personalized outreach)

Predictions are cached for 24 hours per user.
    """
)
async def get_retention_risk(
    user_id: int = Query(..., gt=0, description="User ID to analyze"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get retention risk prediction for a single user.
    
    Returns churn probability, risk band, and recommended action.
    """
    try:
        result = await RetentionRiskService.predict_retention_risk(
            user_id=user_id,
            db=db,
            persist=True
        )
        
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result["error"]
            )
        
        return RetentionRiskResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Retention risk prediction error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {str(e)}"
        )


@router.post(
    "/retention-risk/batch",
    response_model=List[RetentionRiskResponse],
    summary="Batch retention risk prediction",
    description="Predict retention risk for multiple users (max 100)."
)
async def get_retention_risk_batch(
    request: BatchRetentionRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Get retention risk predictions for multiple users.
    """
    try:
        results = await RetentionRiskService.predict_batch(
            user_ids=request.user_ids,
            db=db,
            persist=True
        )
        
        # Filter successful predictions
        responses = []
        for result in results:
            if "error" not in result:
                responses.append(RetentionRiskResponse(**result))
        
        return responses
        
    except Exception as e:
        logger.error(f"Batch retention risk error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch prediction failed: {str(e)}"
        )


@router.get(
    "/retention-risk/high-risk-users",
    response_model=List[HighRiskUserResponse],
    summary="Get high risk users",
    description="Get list of users with high churn risk (for proactive retention campaigns)."
)
async def get_high_risk_users(
    limit: int = Query(100, ge=1, le=500, description="Maximum users to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get users with high retention risk.
    
    Returns users sorted by churn probability (highest first).
    """
    try:
        results = await RetentionRiskService.get_high_risk_users(
            db=db,
            limit=limit
        )
        
        return [HighRiskUserResponse(**r) for r in results]
        
    except Exception as e:
        logger.error(f"High risk users fetch error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch high risk users: {str(e)}"
        )


@router.get(
    "/retention-risk/features",
    summary="Get feature definitions",
    description="Get list of features used for retention risk prediction."
)
async def get_feature_definitions():
    """
    Get feature definitions and descriptions.
    """
    return {
        "features": RetentionRiskService.FEATURE_NAMES,
        "descriptions": {
            "days_since_last_login": "Days since user's last login to the platform",
            "days_since_last_event": "Days since user attended their last event",
            "events_attended_30d": "Number of events attended in last 30 days",
            "events_attended_60d": "Number of events attended in last 60 days",
            "events_attended_90d": "Number of events attended in last 90 days",
            "messages_sent_30d": "Messages sent in last 30 days",
            "blog_interactions_30d": "Blog post views/comments in last 30 days",
            "event_interactions_30d": "Event views/RSVPs in last 30 days",
            "notification_open_ratio": "Ratio of notifications opened vs sent (0-1)",
            "reward_tier": "User's reward tier (0-5 scale)",
            "has_purchase": "Whether user has made a purchase (0 or 1)"
        },
        "risk_thresholds": RetentionRiskService.RISK_THRESHOLDS,
        "recommended_actions": RetentionRiskService.RECOMMENDED_ACTIONS
    }


@router.get(
    "/retention-risk/model-info",
    summary="Get model information",
    description="Get information about the churn prediction model."
)
async def get_model_info():
    """
    Get current model information.
    """
    model_name = RetentionRiskService._get_model_name()
    has_trained_model = RetentionRiskService._load_model() is not None
    
    return {
        "model_name": model_name,
        "model_type": "trained" if has_trained_model else "rule-based",
        "feature_count": len(RetentionRiskService.FEATURE_NAMES),
        "features": RetentionRiskService.FEATURE_NAMES,
        "prediction_cache_hours": 24,
        "description": (
            "Trained scikit-learn model (RandomForest/LogisticRegression)"
            if has_trained_model else
            "Rule-based churn scoring using weighted feature analysis"
        )
    }
