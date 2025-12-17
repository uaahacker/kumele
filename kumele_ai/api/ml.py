"""
ML Router - General ML endpoints including:
- No-Show Prediction (Behavioral Forecasting)
- Attendance Verification (Trust & Fraud Detection)
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from kumele_ai.dependencies import get_db
from kumele_ai.services.no_show_service import no_show_service
from kumele_ai.services.attendance_verification_service import attendance_verification_service

router = APIRouter()


class MLModelInfo(BaseModel):
    name: str
    version: str
    type: str
    status: str


# ============================================================
# NO-SHOW PREDICTION (Behavioral Forecasting)
# ============================================================

class NoShowContext(BaseModel):
    """Context for no-show prediction"""
    price_mode: str = Field(..., description="'paid', 'free', or 'pay_in_person'")
    distance_km: Optional[float] = Field(None, description="Distance from user to event in km")
    rsvp_timestamp: Optional[str] = Field(None, description="ISO timestamp of RSVP")
    event_start_timestamp: Optional[str] = Field(None, description="ISO timestamp of event start")
    payment_completed: Optional[bool] = Field(None, description="Whether payment is complete")
    payment_time_minutes: Optional[float] = Field(None, description="Minutes taken to complete payment")


class NoShowPredictRequest(BaseModel):
    """Request for no-show prediction"""
    user_id: int = Field(..., description="User ID")
    event_id: int = Field(..., description="Event ID")
    context: NoShowContext


class NoShowPredictResponse(BaseModel):
    """Response from no-show prediction"""
    no_show_probability: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    expected_show_probability: Optional[float] = None
    features: Optional[Dict[str, Any]] = None
    model_version: str


class NoShowOutcomeRequest(BaseModel):
    """Request to record no-show outcome"""
    user_id: int
    event_id: int
    outcome: str = Field(..., description="'attended', 'no_show', or 'cancelled'")


class BatchNoShowRequest(BaseModel):
    """Request for batch no-show prediction"""
    event_id: int
    user_ids: List[int]
    context: NoShowContext


@router.post("/no-show/predict", response_model=NoShowPredictResponse)
async def predict_no_show(
    request: NoShowPredictRequest,
    db: Session = Depends(get_db)
):
    """
    Predict no-show probability for a user-event pair.
    
    This is behavioral forecasting for:
    - Pricing Optimization
    - Discount Suggestion Engine
    - Attendance Forecasting
    - Matching/Ranking fairness
    
    NOT moderation. NOT content safety.
    
    **Request:**
    - user_id: User who RSVPed
    - event_id: Event they RSVPed to
    - context: Additional context (price_mode, distance, timestamps)
    
    **Response:**
    - no_show_probability: 0.0 to 1.0 (probability user won't show)
    - confidence: 0.0 to 1.0 (model confidence)
    - expected_show_probability: 1 - no_show_probability
    - features: Extracted features for explainability
    """
    result = no_show_service.predict(
        db=db,
        user_id=request.user_id,
        event_id=request.event_id,
        context=request.context.dict()
    )
    
    return result


@router.post("/no-show/outcome")
async def record_no_show_outcome(
    request: NoShowOutcomeRequest,
    db: Session = Depends(get_db)
):
    """
    Record actual outcome for a no-show prediction.
    
    Used for model training and improvement (feedback loop).
    
    **Outcomes:**
    - 'attended': User attended the event
    - 'no_show': User did not attend
    - 'cancelled': User cancelled before event
    """
    if request.outcome not in ["attended", "no_show", "cancelled"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid outcome. Must be 'attended', 'no_show', or 'cancelled'"
        )
    
    result = no_show_service.record_outcome(
        db=db,
        user_id=request.user_id,
        event_id=request.event_id,
        outcome=request.outcome
    )
    
    return result


@router.post("/no-show/batch-predict")
async def batch_predict_no_show(
    request: BatchNoShowRequest,
    db: Session = Depends(get_db)
):
    """
    Batch predict no-show probabilities for multiple users at an event.
    
    Used for attendance forecasting:
    
    Expected Attendance = Σ(1 - no_show_probability)
    
    **Example:**
    - Capacity = 10
    - Avg no-show prob = 0.30
    - Expected attendance ≈ 7
    
    System can then:
    - Offer stronger discounts
    - Allow controlled overbooking
    - Require upfront payment
    """
    result = no_show_service.batch_predict(
        db=db,
        event_id=request.event_id,
        user_ids=request.user_ids,
        context=request.context.dict()
    )
    
    return result


@router.post("/no-show/update-profile/{user_id}")
async def update_user_attendance_profile(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Update a user's attendance profile based on historical data.
    
    Should be called periodically or after events complete.
    """
    result = no_show_service.update_user_profile(db, user_id)
    return result


# ============================================================
# ATTENDANCE VERIFICATION (Trust & Fraud Detection)
# ============================================================

class AttendanceCheckInData(BaseModel):
    """Check-in data for attendance verification"""
    user_latitude: Optional[float] = Field(None, description="User's GPS latitude")
    user_longitude: Optional[float] = Field(None, description="User's GPS longitude")
    qr_code: Optional[str] = Field(None, description="Scanned QR code or hash")
    qr_scan_timestamp: Optional[str] = Field(None, description="ISO timestamp of QR scan")
    device_hash: Optional[str] = Field(None, description="Device fingerprint hash")
    device_os: Optional[str] = Field(None, description="Device OS")
    app_instance_id: Optional[str] = Field(None, description="App instance identifier")
    host_confirmed: Optional[bool] = Field(None, description="Host manual confirmation")


class AttendanceVerifyRequest(BaseModel):
    """Request for attendance verification"""
    user_id: int = Field(..., description="User attempting check-in")
    event_id: int = Field(..., description="Event being checked into")
    check_in_data: AttendanceCheckInData


class AttendanceVerifyResponse(BaseModel):
    """Response from attendance verification"""
    check_in_status: str = Field(..., description="'Valid', 'Suspicious', or 'Fraudulent'")
    risk_score: float = Field(..., ge=0.0, le=1.0)
    signals: List[str] = Field(default_factory=list)
    action: str = Field(..., description="'accept', 'restrict', or 'escalate_to_support'")
    rewards_unlocked: bool
    reviews_unlocked: bool
    escrow_released: bool
    verification_id: Optional[int] = None
    model_version: str


class SupportDecisionRequest(BaseModel):
    """Request to record support decision on escalated verification"""
    verification_id: int
    decision: str = Field(..., description="'confirmed_valid', 'confirmed_fraud', or 'inconclusive'")
    notes: Optional[str] = None


@router.post("/attendance/verify", response_model=AttendanceVerifyResponse)
async def verify_attendance(
    request: AttendanceVerifyRequest,
    db: Session = Depends(get_db)
):
    """
    Verify a check-in attempt for genuine attendance.
    
    This runs AFTER a check-in attempt to determine if the user
    is genuinely present at the event.
    
    **Purpose:**
    Ensures only genuinely present users can unlock:
    - Rewards & medals
    - Reviews / ratings
    - Refund eligibility
    - Escrow release
    - Host reputation updates
    
    **Signals Checked:**
    1. GPS distance (user vs event location)
    2. GPS spoofing detection
    3. QR timing validation
    4. QR replay detection
    5. Device fingerprinting
    6. Host confirmation
    7. User trust profile
    
    **Statuses:**
    - **Valid**: Attendance confirmed, all unlocks granted
    - **Suspicious**: Temporarily accepted, unlocks blocked, auto-escalated
    - **Fraudulent**: Check-in rejected, penalty applied
    
    NOT content moderation. This is trust & safety AI.
    """
    result = attendance_verification_service.verify(
        db=db,
        user_id=request.user_id,
        event_id=request.event_id,
        check_in_data=request.check_in_data.dict()
    )
    
    return result


@router.post("/attendance/support-decision")
async def record_support_decision(
    request: SupportDecisionRequest,
    db: Session = Depends(get_db)
):
    """
    Record support team's decision on an escalated verification.
    
    **MANDATORY FEEDBACK LOOP:**
    This decision feeds back into:
    - Training data
    - Rule refinement
    - Model improvement
    
    **Decisions:**
    - 'confirmed_valid': False positive, restore user trust, unlock rewards
    - 'confirmed_fraud': Confirmed fraud, apply additional penalty
    - 'inconclusive': Unable to determine, no changes
    """
    if request.decision not in ["confirmed_valid", "confirmed_fraud", "inconclusive"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid decision. Must be 'confirmed_valid', 'confirmed_fraud', or 'inconclusive'"
        )
    
    result = attendance_verification_service.record_support_decision(
        db=db,
        verification_id=request.verification_id,
        decision=request.decision,
        notes=request.notes
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.get("/attendance/history")
async def get_verification_history(
    user_id: Optional[int] = None,
    event_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Get attendance verification history for audit.
    
    Filter by user_id, event_id, or status.
    All decisions are logged with full audit trail.
    """
    result = attendance_verification_service.get_verification_history(
        db=db,
        user_id=user_id,
        event_id=event_id,
        status=status,
        limit=limit
    )
    
    return {"verifications": result, "count": len(result)}


@router.get("/models")
async def list_models(db: Session = Depends(get_db)):
    """
    List all registered ML models.
    """
    from kumele_ai.db.models import AIModelRegistry
    
    models = db.query(AIModelRegistry).all()
    
    return {
        "models": [
            {
                "name": m.name,
                "version": m.version,
                "type": m.type,
                "status": m.status,
                "loaded_at": m.loaded_at.isoformat() if m.loaded_at else None
            }
            for m in models
        ]
    }


@router.get("/models/{model_name}")
async def get_model_info(
    model_name: str,
    db: Session = Depends(get_db)
):
    """
    Get information about a specific model.
    """
    from kumele_ai.db.models import AIModelRegistry
    
    model = db.query(AIModelRegistry).filter(
        AIModelRegistry.name == model_name
    ).first()
    
    if not model:
        return {"error": "Model not found"}
    
    return {
        "name": model.name,
        "version": model.version,
        "type": model.type,
        "status": model.status,
        "loaded_at": model.loaded_at.isoformat() if model.loaded_at else None,
        "config": model.config
    }
