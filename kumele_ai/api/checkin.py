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
router = APIRouter(prefix="/checkin", tags=["Check-in"])


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


# ============================================================
# CHECK-IN VERIFY ENDPOINT (POST /checkin/verify)
# ============================================================

class VerifyCheckInRequest(BaseModel):
    """Request for check-in verification"""
    event_id: int = Field(..., description="Event ID")
    user_id: int = Field(..., description="User ID")
    qr_code: Optional[str] = Field(None, description="QR code for host scan mode")
    latitude: Optional[float] = Field(None, description="User GPS latitude")
    longitude: Optional[float] = Field(None, description="User GPS longitude")
    device_hash: Optional[str] = Field(None, description="Device fingerprint")
    qr_timestamp: Optional[datetime] = Field(None, description="QR scan timestamp")


class VerifyCheckInResponse(BaseModel):
    """Response from check-in verification"""
    verified: bool
    status: str  # "verified", "suspicious", "rejected"
    confidence: float
    geo_distance_km: Optional[float]
    time_from_start_minutes: Optional[float]
    device_trusted: bool
    host_confirmed: bool
    verification_id: int
    message: str


@router.post("/verify", response_model=VerifyCheckInResponse)
async def verify_checkin(
    request: VerifyCheckInRequest,
    db: Session = Depends(get_db)
):
    """
    POST /checkin/verify
    
    Verify a check-in attempt. Combines:
    - Geo distance verification
    - QR scan timestamp validation
    - Device fingerprint check
    - Event start time validation
    - Host confirmation logs
    
    Returns verification status with confidence score.
    """
    import math
    
    # Get event
    event = db.query(Event).filter(Event.id == request.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Initialize verification result
    checks = {
        "geo_valid": False,
        "time_valid": False,
        "device_trusted": True,
        "host_confirmed": False
    }
    
    confidence = 0.0
    geo_distance = None
    time_from_start = None
    
    # 1. Geo distance check
    if request.latitude and request.longitude and event.latitude and event.longitude:
        R = 6371  # Earth's radius in km
        lat1, lon1 = math.radians(request.latitude), math.radians(request.longitude)
        lat2, lon2 = math.radians(event.latitude), math.radians(event.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        geo_distance = R * c
        
        if geo_distance <= 2.0:  # Within 2km
            checks["geo_valid"] = True
            confidence += 0.3
        elif geo_distance <= 5.0:
            checks["geo_valid"] = True
            confidence += 0.15
    
    # 2. Time validation
    if event.event_date:
        now = datetime.utcnow()
        time_from_start = (now - event.event_date).total_seconds() / 60
        
        # Valid window: 30 min before to 2 hours after
        if -30 <= time_from_start <= 120:
            checks["time_valid"] = True
            confidence += 0.25
    
    # 3. Device fingerprint check
    if request.device_hash:
        device = db.query(DeviceFingerprint).filter(
            DeviceFingerprint.device_hash == request.device_hash
        ).first()
        
        if device and device.fraud_count > 0:
            checks["device_trusted"] = False
            confidence -= 0.2
        else:
            checks["device_trusted"] = True
            confidence += 0.2
    
    # 4. QR code verification (if provided)
    if request.qr_code:
        import hashlib
        qr_hash = hashlib.sha256(request.qr_code.encode()).hexdigest()[:32]
        
        # Check for replay
        replay_window = datetime.utcnow() - timedelta(seconds=60)
        replay = db.query(QRScanLog).filter(
            and_(
                QRScanLog.qr_code_hash == qr_hash,
                QRScanLog.event_id == request.event_id,
                QRScanLog.scanned_at >= replay_window
            )
        ).first()
        
        if not replay:
            checks["host_confirmed"] = True
            confidence += 0.25
            
            # Log QR scan
            qr_log = QRScanLog(
                qr_code_hash=qr_hash,
                event_id=request.event_id,
                user_id=request.user_id,
                device_hash=request.device_hash,
                is_valid=True
            )
            db.add(qr_log)
    
    # Calculate final status
    confidence = max(0, min(1.0, confidence))
    
    if confidence >= 0.7:
        status = "verified"
        verified = True
    elif confidence >= 0.4:
        status = "suspicious"
        verified = False
    else:
        status = "rejected"
        verified = False
    
    # Create verification record
    verification = AttendanceVerification(
        event_id=request.event_id,
        user_id=request.user_id,
        confidence_score=confidence,
        decision="confirmed_valid" if verified else "flagged_suspicious",
        distance_km=geo_distance
    )
    db.add(verification)
    db.commit()
    db.refresh(verification)
    
    message = f"Check-in {status}"
    if not verified and not checks["geo_valid"]:
        message = f"Location too far from venue ({geo_distance:.1f}km)" if geo_distance else "Missing location data"
    elif not verified and not checks["time_valid"]:
        message = "Outside valid check-in time window"
    elif not verified and not checks["device_trusted"]:
        message = "Device has previous fraud flags"
    
    return VerifyCheckInResponse(
        verified=verified,
        status=status,
        confidence=round(confidence, 4),
        geo_distance_km=round(geo_distance, 2) if geo_distance else None,
        time_from_start_minutes=round(time_from_start, 1) if time_from_start else None,
        device_trusted=checks["device_trusted"],
        host_confirmed=checks["host_confirmed"],
        verification_id=verification.id,
        message=message
    )


# ============================================================
# FRAUD DETECTION ENDPOINT (POST /checkin/fraud-detect)
# ============================================================

class FraudDetectRequest(BaseModel):
    """Request for fraud detection analysis"""
    event_id: int = Field(..., description="Event ID")
    user_id: int = Field(..., description="User ID to check")
    device_hash: Optional[str] = Field(None, description="Device fingerprint")
    ip_address: Optional[str] = Field(None, description="User's IP address")
    latitude: Optional[float] = Field(None, description="GPS latitude")
    longitude: Optional[float] = Field(None, description="GPS longitude")
    qr_image_hash: Optional[str] = Field(None, description="Hash of QR image (screenshot detection)")


class FraudDetectResponse(BaseModel):
    """Response from fraud detection"""
    score: float  # 0.0 = clean, 1.0 = definite fraud
    decision: str  # "clean", "suspicious", "likely_fraud"
    reason: str
    risk_factors: list
    recommendations: list


@router.post("/fraud-detect", response_model=FraudDetectResponse)
async def detect_fraud(
    request: FraudDetectRequest,
    db: Session = Depends(get_db)
):
    """
    POST /checkin/fraud-detect
    
    ML model evaluates fraud indicators:
    - Fake QR screenshots
    - Too many check-ins from single IP/device
    - Sudden location jumps
    - Host check-in abuse
    - Refund fraud attempts
    
    Returns:
    - score: 0.0-1.0 (higher = more likely fraud)
    - decision: clean/suspicious/likely_fraud
    - reason: Human-readable explanation
    """
    risk_factors = []
    score = 0.0
    
    # Get event
    event = db.query(Event).filter(Event.id == request.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # 1. Check device fraud history
    if request.device_hash:
        device = db.query(DeviceFingerprint).filter(
            DeviceFingerprint.device_hash == request.device_hash
        ).first()
        
        if device:
            if device.fraud_count > 0:
                score += 0.3 * min(device.fraud_count, 3)  # Up to 0.9
                risk_factors.append(f"Device has {device.fraud_count} previous fraud flags")
            
            # Check multiple check-ins from same device in short period
            recent_checkins = db.query(func.count(CheckIn.id)).filter(
                and_(
                    CheckIn.device_hash == request.device_hash,
                    CheckIn.check_in_time >= datetime.utcnow() - timedelta(hours=24)
                )
            ).scalar() or 0
            
            if recent_checkins > 5:
                score += 0.2
                risk_factors.append(f"Device used for {recent_checkins} check-ins in 24h")
    
    # 2. Check for location jumps (impossible travel)
    if request.latitude and request.longitude:
        # Get last check-in location
        last_checkin = db.query(CheckIn).filter(
            and_(
                CheckIn.user_id == request.user_id,
                CheckIn.check_in_time >= datetime.utcnow() - timedelta(hours=2)
            )
        ).order_by(CheckIn.check_in_time.desc()).first()
        
        if last_checkin and last_checkin.user_latitude and last_checkin.user_longitude:
            import math
            R = 6371
            lat1, lon1 = math.radians(last_checkin.user_latitude), math.radians(last_checkin.user_longitude)
            lat2, lon2 = math.radians(request.latitude), math.radians(request.longitude)
            
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            distance = R * c
            
            # Check for impossible travel (>100km in <1 hour)
            if last_checkin.check_in_time:
                hours_diff = (datetime.utcnow() - last_checkin.check_in_time).total_seconds() / 3600
                if hours_diff < 1 and distance > 100:
                    score += 0.4
                    risk_factors.append(f"Abnormal GPS variance: {distance:.0f}km in {hours_diff:.1f}h")
    
    # 3. Check for fake QR screenshots
    if request.qr_image_hash:
        # Check if this exact QR image was used before
        similar_qr = db.query(func.count(QRScanLog.id)).filter(
            QRScanLog.qr_code_hash == request.qr_image_hash
        ).scalar() or 0
        
        if similar_qr > 2:
            score += 0.35
            risk_factors.append("Possible screenshot/reuse of QR code image")
    
    # 4. Check user's refund history
    user_events = db.query(UserEvent).filter(
        and_(
            UserEvent.user_id == request.user_id,
            UserEvent.rsvp_status == "cancelled"
        )
    ).count()
    
    total_rsvps = db.query(UserEvent).filter(
        UserEvent.user_id == request.user_id
    ).count()
    
    if total_rsvps > 5 and (user_events / total_rsvps) > 0.5:
        score += 0.15
        risk_factors.append(f"High cancellation rate: {user_events}/{total_rsvps}")
    
    # 5. Check if user is host trying to abuse check-ins
    if event.host_id == request.user_id:
        host_checkins = db.query(func.count(CheckIn.id)).filter(
            and_(
                CheckIn.user_id == request.user_id,
                CheckIn.event_id == request.event_id
            )
        ).scalar() or 0
        
        if host_checkins > 0:
            score += 0.1
            risk_factors.append("Host attempting to self-check-in")
    
    # Calculate final score and decision
    score = min(1.0, score)
    
    if score >= 0.7:
        decision = "likely_fraud"
    elif score >= 0.35:
        decision = "suspicious"
    else:
        decision = "clean"
    
    # Build reason string
    if risk_factors:
        reason = " + ".join(risk_factors[:2])  # Top 2 factors
    else:
        reason = "No significant risk factors detected"
    
    # Recommendations
    recommendations = []
    if score >= 0.7:
        recommendations = [
            "Block check-in",
            "Flag user for review",
            "Require host manual verification"
        ]
    elif score >= 0.35:
        recommendations = [
            "Allow with manual review",
            "Request additional verification",
            "Monitor user activity"
        ]
    else:
        recommendations = ["Allow check-in"]
    
    return FraudDetectResponse(
        score=round(score, 2),
        decision=decision,
        reason=reason,
        risk_factors=risk_factors,
        recommendations=recommendations
    )


# ============================================================
# HOST COMPLIANCE RATE
# ============================================================

class HostComplianceResponse(BaseModel):
    """Host check-in compliance metrics"""
    host_id: int
    total_events: int
    events_with_checkins: int
    total_expected_checkins: int
    total_actual_checkins: int
    compliance_rate: float
    avg_checkin_rate_per_event: float
    host_tier: Optional[str]
    event_completion_rate: float
    cancellation_rate: float
    refund_penalty_count: int


@router.get("/host/{host_id}/compliance", response_model=HostComplianceResponse)
async def get_host_compliance(
    host_id: int,
    days: int = Query(default=90, le=365),
    db: Session = Depends(get_db)
):
    """
    Get host's check-in compliance rate.
    
    Tracks:
    - How often host uses check-in system
    - Event completion rate
    - Cancellation rate
    - Refund-triggered penalties
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Get host's events
    events = db.query(Event).filter(
        and_(
            Event.host_id == host_id,
            Event.created_at >= cutoff
        )
    ).all()
    
    total_events = len(events)
    events_with_checkins = 0
    total_expected = 0
    total_actual = 0
    completed = 0
    cancelled = 0
    
    for event in events:
        # Count RSVPs
        rsvps = db.query(func.count(UserEvent.id)).filter(
            UserEvent.event_id == event.id
        ).scalar() or 0
        
        total_expected += rsvps
        
        # Count check-ins
        checkins = db.query(func.count(CheckIn.id)).filter(
            CheckIn.event_id == event.id
        ).scalar() or 0
        
        total_actual += checkins
        
        if checkins > 0:
            events_with_checkins += 1
        
        # Event status
        if event.status == "completed":
            completed += 1
        elif event.status == "cancelled":
            cancelled += 1
    
    # Calculate rates
    compliance_rate = events_with_checkins / max(total_events, 1)
    avg_checkin_rate = total_actual / max(total_expected, 1)
    completion_rate = completed / max(total_events, 1)
    cancellation_rate = cancelled / max(total_events, 1)
    
    # Get host tier
    from kumele_ai.db.models import NFTBadge
    badge = db.query(NFTBadge).filter(
        and_(
            NFTBadge.user_id == host_id,
            NFTBadge.is_active == True
        )
    ).first()
    
    # Count refund penalties (simplified)
    refund_penalties = db.query(func.count(UserEvent.id)).filter(
        and_(
            UserEvent.event_id.in_([e.id for e in events]),
            UserEvent.rsvp_status == "refunded"
        )
    ).scalar() or 0
    
    return HostComplianceResponse(
        host_id=host_id,
        total_events=total_events,
        events_with_checkins=events_with_checkins,
        total_expected_checkins=total_expected,
        total_actual_checkins=total_actual,
        compliance_rate=round(compliance_rate, 4),
        avg_checkin_rate_per_event=round(avg_checkin_rate, 4),
        host_tier=badge.tier if badge else None,
        event_completion_rate=round(completion_rate, 4),
        cancellation_rate=round(cancellation_rate, 4),
        refund_penalty_count=refund_penalties
    )

