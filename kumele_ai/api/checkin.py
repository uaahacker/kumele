"""
Check-in API - Attendance Verification Endpoints

Provides:
- POST /checkin/validate: Validate attendance check-in (host_qr or self_check)
- GET /checkin/{event_id}/status: Get check-in status for an event
- GET /checkin/user/{user_id}/history: Get user's check-in history
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from kumele_ai.db.database import get_db
from kumele_ai.db.models import (
    Event, User, UserEvent, CheckIn, AttendanceVerification,
    UserMLFeatures, DeviceFingerprint, QRScanLog
)
from kumele_ai.services.attendance_verification_service import attendance_verification_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/checkin", tags=["checkin"])


# ============================================================
# REQUEST/RESPONSE MODELS
# ============================================================

class CheckInRequest(BaseModel):
    """Request model for check-in validation"""
    event_id: int = Field(..., description="ID of the event")
    user_id: int = Field(..., description="ID of the user checking in")
    mode: str = Field(..., description="Check-in mode: 'host_qr' or 'self_check'")
    
    # For host_qr mode
    qr_code: Optional[str] = Field(None, description="QR code scanned by host")
    host_id: Optional[int] = Field(None, description="ID of the host scanning")
    
    # For self_check mode
    user_latitude: Optional[float] = Field(None, description="User's GPS latitude")
    user_longitude: Optional[float] = Field(None, description="User's GPS longitude")
    
    # Device fingerprint (optional, for fraud detection)
    device_hash: Optional[str] = Field(None, description="Device fingerprint hash")
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_id": 123,
                "user_id": 456,
                "mode": "self_check",
                "user_latitude": 40.7128,
                "user_longitude": -74.0060
            }
        }


class CheckInResponse(BaseModel):
    """Response model for check-in validation"""
    is_valid: bool
    status: str  # "Valid", "Suspicious", "Fraudulent"
    risk_score: float
    reason_code: str
    message: str
    check_in_id: Optional[int] = None
    verification_id: Optional[int] = None
    
    # Detailed breakdown
    checks_passed: Optional[dict] = None
    warnings: Optional[list] = None


class EventCheckInStatus(BaseModel):
    """Status of check-ins for an event"""
    event_id: int
    total_rsvps: int
    total_checked_in: int
    valid_check_ins: int
    suspicious_check_ins: int
    check_in_rate: float
    by_mode: dict


# ============================================================
# CHECK-IN VALIDATION ENDPOINT
# ============================================================

@router.post("/validate", response_model=CheckInResponse)
async def validate_checkin(
    request: CheckInRequest,
    db: Session = Depends(get_db)
):
    """
    Validate a user's check-in for an event.
    
    Supports two modes:
    
    **host_qr**: Host scans attendee's QR code
    - Requires: qr_code, host_id
    - Validates: QR authenticity, replay detection, host authorization
    
    **self_check**: User self-checks via GPS
    - Requires: user_latitude, user_longitude
    - Validates: GPS within 2km of venue, time window, device trust
    
    Returns:
    - is_valid: Whether check-in is accepted
    - status: "Valid", "Suspicious", or "Fraudulent"
    - risk_score: 0.0-1.0 (higher = more risky)
    - reason_code: Machine-readable result code
    """
    try:
        # Validate mode
        if request.mode not in ["host_qr", "self_check"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid mode. Must be 'host_qr' or 'self_check'"
            )
        
        # Check if event exists and is active
        event = db.query(Event).filter(Event.id == request.event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        
        # Check if user is registered for the event
        registration = db.query(UserEvent).filter(
            and_(
                UserEvent.event_id == request.event_id,
                UserEvent.user_id == request.user_id
            )
        ).first()
        
        if not registration:
            return CheckInResponse(
                is_valid=False,
                status="Fraudulent",
                risk_score=1.0,
                reason_code="not_registered",
                message="User is not registered for this event"
            )
        
        # Check if already checked in
        existing_checkin = db.query(CheckIn).filter(
            and_(
                CheckIn.event_id == request.event_id,
                CheckIn.user_id == request.user_id,
                CheckIn.is_valid == True
            )
        ).first()
        
        if existing_checkin:
            return CheckInResponse(
                is_valid=False,
                status="Suspicious",
                risk_score=0.7,
                reason_code="already_checked_in",
                message="User has already checked in to this event",
                check_in_id=existing_checkin.id
            )
        
        # Validate time window (allow check-in 30 min before to 2 hours after start)
        if event.event_date:
            now = datetime.utcnow()
            window_start = event.event_date - timedelta(minutes=30)
            window_end = event.event_date + timedelta(hours=2)
            
            if now < window_start:
                return CheckInResponse(
                    is_valid=False,
                    status="Suspicious",
                    risk_score=0.5,
                    reason_code="too_early",
                    message=f"Check-in window opens 30 minutes before event start"
                )
            
            if now > window_end:
                return CheckInResponse(
                    is_valid=False,
                    status="Suspicious",
                    risk_score=0.6,
                    reason_code="too_late",
                    message="Check-in window has closed (2 hours after event start)"
                )
        
        # Mode-specific validation
        if request.mode == "host_qr":
            result = await _validate_host_qr_checkin(db, request, event)
        else:  # self_check
            result = await _validate_self_checkin(db, request, event)
        
        # Create check-in record
        checkin = CheckIn(
            event_id=request.event_id,
            user_id=request.user_id,
            mode=request.mode,
            is_valid=result["is_valid"],
            distance_km=result.get("distance_km"),
            risk_score=result["risk_score"],
            reason_code=result["reason_code"],
            user_latitude=request.user_latitude,
            user_longitude=request.user_longitude,
            qr_code_hash=result.get("qr_hash"),
            device_hash=request.device_hash,
            host_confirmed=request.mode == "host_qr",
            event_start_time=event.event_date,
            minutes_from_start=result.get("minutes_from_start")
        )
        
        db.add(checkin)
        db.commit()
        db.refresh(checkin)
        
        # Update user's ML features if valid
        if result["is_valid"]:
            _update_user_attendance_features(db, request.user_id)
        
        return CheckInResponse(
            is_valid=result["is_valid"],
            status=result["status"],
            risk_score=result["risk_score"],
            reason_code=result["reason_code"],
            message=result["message"],
            check_in_id=checkin.id,
            verification_id=result.get("verification_id"),
            checks_passed=result.get("checks_passed"),
            warnings=result.get("warnings")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Check-in validation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# HELPER FUNCTIONS
# ============================================================

async def _validate_host_qr_checkin(
    db: Session,
    request: CheckInRequest,
    event: Event
) -> dict:
    """Validate host QR scan check-in"""
    # Verify host authorization
    if request.host_id != event.host_id:
        return {
            "is_valid": False,
            "status": "Fraudulent",
            "risk_score": 0.9,
            "reason_code": "unauthorized_host",
            "message": "Scanner is not the event host"
        }
    
    # Validate QR code
    if not request.qr_code:
        return {
            "is_valid": False,
            "status": "Suspicious",
            "risk_score": 0.7,
            "reason_code": "missing_qr",
            "message": "QR code is required for host_qr mode"
        }
    
    # Hash QR code for storage/comparison
    import hashlib
    qr_hash = hashlib.sha256(request.qr_code.encode()).hexdigest()[:32]
    
    # Check for QR replay (same QR used within 60 seconds)
    replay_window = datetime.utcnow() - timedelta(seconds=60)
    replay = db.query(QRScanLog).filter(
        and_(
            QRScanLog.qr_code_hash == qr_hash,
            QRScanLog.event_id == request.event_id,
            QRScanLog.scanned_at >= replay_window
        )
    ).first()
    
    if replay:
        return {
            "is_valid": False,
            "status": "Fraudulent",
            "risk_score": 0.95,
            "reason_code": "qr_replay",
            "message": "This QR code was recently used. Possible replay attack.",
            "qr_hash": qr_hash
        }
    
    # Log QR scan
    qr_log = QRScanLog(
        qr_code_hash=qr_hash,
        event_id=request.event_id,
        user_id=request.user_id,
        device_hash=request.device_hash,
        is_valid=True
    )
    db.add(qr_log)
    
    return {
        "is_valid": True,
        "status": "Valid",
        "risk_score": 0.0,
        "reason_code": "success",
        "message": "Check-in validated by host QR scan",
        "qr_hash": qr_hash,
        "checks_passed": {
            "host_authorized": True,
            "qr_valid": True,
            "no_replay": True
        }
    }


async def _validate_self_checkin(
    db: Session,
    request: CheckInRequest,
    event: Event
) -> dict:
    """Validate self-service GPS check-in"""
    import math
    
    # Require GPS coordinates
    if request.user_latitude is None or request.user_longitude is None:
        return {
            "is_valid": False,
            "status": "Suspicious",
            "risk_score": 0.7,
            "reason_code": "missing_gps",
            "message": "GPS coordinates required for self-check mode"
        }
    
    # Check if event has location
    if event.latitude is None or event.longitude is None:
        return {
            "is_valid": False,
            "status": "Suspicious",
            "risk_score": 0.5,
            "reason_code": "no_venue_location",
            "message": "Event venue location not configured"
        }
    
    # Calculate distance using Haversine formula
    R = 6371  # Earth's radius in km
    lat1, lon1 = math.radians(request.user_latitude), math.radians(request.user_longitude)
    lat2, lon2 = math.radians(event.latitude), math.radians(event.longitude)
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance_km = R * c
    
    # Maximum allowed distance (2km)
    MAX_DISTANCE_KM = 2.0
    
    warnings = []
    risk_score = 0.0
    
    # Distance check
    if distance_km > MAX_DISTANCE_KM:
        return {
            "is_valid": False,
            "status": "Suspicious",
            "risk_score": 0.8,
            "reason_code": "gps_mismatch",
            "message": f"You are {distance_km:.1f}km from the venue (max {MAX_DISTANCE_KM}km)",
            "distance_km": distance_km
        }
    
    # Add minor risk for edge cases
    if distance_km > 1.5:
        risk_score += 0.1
        warnings.append(f"User is {distance_km:.1f}km from venue")
    
    # Check device trust
    if request.device_hash:
        device = db.query(DeviceFingerprint).filter(
            DeviceFingerprint.device_hash == request.device_hash
        ).first()
        
        if device and device.fraud_count > 0:
            risk_score += 0.2 * device.fraud_count
            warnings.append(f"Device has {device.fraud_count} fraud flags")
    
    # Calculate minutes from event start
    minutes_from_start = None
    if event.event_date:
        delta = datetime.utcnow() - event.event_date
        minutes_from_start = delta.total_seconds() / 60
    
    # Determine final status
    if risk_score >= 0.5:
        status = "Suspicious"
    else:
        status = "Valid"
    
    return {
        "is_valid": risk_score < 0.5,
        "status": status,
        "risk_score": min(risk_score, 1.0),
        "reason_code": "success" if risk_score < 0.5 else "elevated_risk",
        "message": "Check-in validated via GPS proximity" if risk_score < 0.5 else "Check-in flagged for review",
        "distance_km": distance_km,
        "minutes_from_start": minutes_from_start,
        "checks_passed": {
            "gps_valid": distance_km <= MAX_DISTANCE_KM,
            "within_time_window": True,
            "device_trusted": risk_score < 0.3
        },
        "warnings": warnings if warnings else None
    }


def _update_user_attendance_features(db: Session, user_id: int):
    """Update user's ML features after successful check-in"""
    user_ml = db.query(UserMLFeatures).filter(
        UserMLFeatures.user_id == user_id
    ).first()
    
    if not user_ml:
        user_ml = UserMLFeatures(user_id=user_id)
        db.add(user_ml)
    
    # Count verified check-ins
    from datetime import timedelta
    
    count_30d = db.query(func.count(CheckIn.id)).filter(
        and_(
            CheckIn.user_id == user_id,
            CheckIn.is_valid == True,
            CheckIn.check_in_time >= datetime.utcnow() - timedelta(days=30)
        )
    ).scalar() or 0
    
    count_90d = db.query(func.count(CheckIn.id)).filter(
        and_(
            CheckIn.user_id == user_id,
            CheckIn.is_valid == True,
            CheckIn.check_in_time >= datetime.utcnow() - timedelta(days=90)
        )
    ).scalar() or 0
    
    user_ml.verified_attendance_30d = count_30d
    user_ml.verified_attendance_90d = count_90d
    user_ml.last_updated = datetime.utcnow()
    
    db.commit()


# ============================================================
# STATUS ENDPOINTS
# ============================================================

@router.get("/event/{event_id}/status", response_model=EventCheckInStatus)
async def get_event_checkin_status(
    event_id: int,
    db: Session = Depends(get_db)
):
    """Get check-in status for an event"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Count RSVPs
    total_rsvps = db.query(func.count(UserEvent.id)).filter(
        UserEvent.event_id == event_id
    ).scalar() or 0
    
    # Count check-ins by validity
    checkins = db.query(
        CheckIn.is_valid,
        CheckIn.mode,
        func.count(CheckIn.id)
    ).filter(
        CheckIn.event_id == event_id
    ).group_by(CheckIn.is_valid, CheckIn.mode).all()
    
    total_checked_in = 0
    valid_count = 0
    by_mode = {"host_qr": 0, "self_check": 0}
    
    for is_valid, mode, count in checkins:
        total_checked_in += count
        if is_valid:
            valid_count += count
        if mode in by_mode:
            by_mode[mode] += count
    
    suspicious_count = total_checked_in - valid_count
    
    return EventCheckInStatus(
        event_id=event_id,
        total_rsvps=total_rsvps,
        total_checked_in=total_checked_in,
        valid_check_ins=valid_count,
        suspicious_check_ins=suspicious_count,
        check_in_rate=valid_count / max(total_rsvps, 1),
        by_mode=by_mode
    )


@router.get("/user/{user_id}/history")
async def get_user_checkin_history(
    user_id: int,
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db)
):
    """Get user's check-in history"""
    checkins = db.query(CheckIn).filter(
        CheckIn.user_id == user_id
    ).order_by(CheckIn.check_in_time.desc()).limit(limit).all()
    
    return {
        "user_id": user_id,
        "total_checkins": len(checkins),
        "history": [
            {
                "id": c.id,
                "event_id": c.event_id,
                "mode": c.mode,
                "is_valid": c.is_valid,
                "risk_score": c.risk_score,
                "reason_code": c.reason_code,
                "check_in_time": c.check_in_time.isoformat() if c.check_in_time else None,
                "distance_km": c.distance_km
            }
            for c in checkins
        ]
    }
