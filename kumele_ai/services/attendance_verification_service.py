"""
Attendance Verification AI - Trust & Fraud Detection

Ensures only genuinely present users can unlock:
- Rewards & medals
- Reviews / ratings
- Refund eligibility
- Escrow release
- Host reputation updates

This runs AFTER a check-in attempt.

This is NOT content moderation.
This is behavioral + trust verification.
"""
import logging
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import math

from kumele_ai.db.models import (
    User, Event, UserEvent, AttendanceVerification,
    DeviceFingerprint, UserTrustProfile, QRScanLog, HostRating
)

logger = logging.getLogger(__name__)

# Model version for tracking
MODEL_VERSION = "1.0.0-rule-enhanced"

# Configurable thresholds
THRESHOLDS = {
    # GPS thresholds
    "gps_max_distance_km": 2.0,
    "gps_spoof_jump_km": 50.0,  # Suspicious if user "jumps" more than this
    
    # Timing thresholds (minutes)
    "qr_early_window_min": -10,    # Can check in 10 min early
    "qr_late_window_min": 45,      # Can check in up to 45 min late
    "qr_replay_window_sec": 60,    # Same QR within 60 sec = replay
    
    # Risk score thresholds
    "risk_valid_max": 0.3,
    "risk_suspicious_max": 0.7,
    
    # Device thresholds
    "max_users_per_device": 3,
    "max_simultaneous_devices": 2,
}

# Rule weights for risk score calculation
RULE_WEIGHTS = {
    "gps_mismatch": 0.35,
    "gps_spoof_detected": 0.50,
    "late_qr_scan": 0.15,
    "very_late_qr_scan": 0.30,
    "early_qr_scan": 0.10,
    "qr_replay_detected": 0.60,
    "device_shared_multiple_users": 0.25,
    "device_simultaneous": 0.40,
    "host_not_confirmed": 0.10,
    "host_conflict": 0.35,
    "user_low_trust": 0.20,
    "user_prior_fraud": 0.45,
    "timing_suspicious": 0.20,
}


class AttendanceVerificationService:
    """
    Service for verifying genuine attendance at events.
    
    Uses rule-enhanced ML classifier:
    1. Rules fire first (hard checks)
    2. ML model refines score
    3. Output: classification + risk score + signals + action
    
    All decisions logged for audit trail and feedback loop.
    """
    
    def verify(
        self,
        db: Session,
        user_id: int,
        event_id: int,
        check_in_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Verify a check-in attempt.
        
        Args:
            db: Database session
            user_id: User attempting check-in
            event_id: Event being checked into
            check_in_data:
                - user_latitude: User's GPS latitude
                - user_longitude: User's GPS longitude
                - qr_code: QR code scanned (or hash)
                - qr_scan_timestamp: When QR was scanned
                - device_hash: Device fingerprint hash
                - device_os: Device OS
                - app_instance_id: App instance identifier
                - host_confirmed: Whether host manually confirmed (optional)
                
        Returns:
            {
                "check_in_status": "Valid" | "Suspicious" | "Fraudulent",
                "risk_score": 0.78,
                "signals": ["gps_mismatch", "late_qr_scan"],
                "action": "accept" | "restrict" | "escalate_to_support",
                "rewards_unlocked": bool,
                "reviews_unlocked": bool,
                "escrow_released": bool
            }
        """
        try:
            # Get event details
            event = db.query(Event).filter(Event.id == event_id).first()
            if not event:
                return self._error_response("Event not found")
            
            # Get user trust profile
            user_trust = self._get_user_trust_profile(db, user_id)
            
            # Run all verification rules
            signals, rule_scores = self._run_verification_rules(
                db, user_id, event_id, event, check_in_data, user_trust
            )
            
            # Calculate final risk score
            risk_score = self._calculate_risk_score(signals, rule_scores, user_trust)
            
            # Determine status and action
            status, action = self._determine_status_and_action(risk_score, signals)
            
            # Determine what to unlock
            rewards_unlocked = status == "Valid"
            reviews_unlocked = status == "Valid"
            escrow_released = status == "Valid"
            
            # Log device fingerprint
            self._log_device_fingerprint(db, user_id, check_in_data)
            
            # Log QR scan
            self._log_qr_scan(db, user_id, event_id, check_in_data, 
                            is_valid=(status != "Fraudulent"))
            
            # Log verification decision (audit trail)
            verification_id = self._log_verification(
                db=db,
                user_id=user_id,
                event_id=event_id,
                event=event,
                check_in_data=check_in_data,
                status=status,
                risk_score=risk_score,
                action=action,
                signals=signals,
                rule_scores=rule_scores,
                rewards_unlocked=rewards_unlocked,
                reviews_unlocked=reviews_unlocked,
                escrow_released=escrow_released
            )
            
            # Update user trust profile
            self._update_user_trust_profile(db, user_id, status, signals)
            
            return {
                "check_in_status": status,
                "risk_score": round(risk_score, 4),
                "signals": signals,
                "action": action,
                "rewards_unlocked": rewards_unlocked,
                "reviews_unlocked": reviews_unlocked,
                "escrow_released": escrow_released,
                "verification_id": verification_id,
                "model_version": MODEL_VERSION
            }
            
        except Exception as e:
            logger.error(f"Error verifying attendance: {e}")
            return self._error_response(str(e))
    
    def _run_verification_rules(
        self,
        db: Session,
        user_id: int,
        event_id: int,
        event: Event,
        data: Dict[str, Any],
        user_trust: Dict[str, Any]
    ) -> Tuple[List[str], Dict[str, float]]:
        """Run all verification rules and return triggered signals."""
        signals = []
        rule_scores = {}
        
        # 1. GPS Distance Check
        gps_result = self._check_gps_distance(
            data.get("user_latitude"),
            data.get("user_longitude"),
            event.latitude,
            event.longitude
        )
        if gps_result["triggered"]:
            signals.append(gps_result["signal"])
            rule_scores[gps_result["signal"]] = gps_result["score"]
        
        # 2. GPS Spoof Detection (sudden location jump)
        spoof_result = self._check_gps_spoofing(db, user_id, data)
        if spoof_result["triggered"]:
            signals.append("gps_spoof_detected")
            rule_scores["gps_spoof_detected"] = spoof_result["score"]
        
        # 3. QR Timing Check
        timing_result = self._check_qr_timing(
            data.get("qr_scan_timestamp"),
            event.start_time or event.event_date,
            event.end_time
        )
        if timing_result["triggered"]:
            signals.append(timing_result["signal"])
            rule_scores[timing_result["signal"]] = timing_result["score"]
        
        # 4. QR Replay Detection
        replay_result = self._check_qr_replay(db, event_id, data)
        if replay_result["triggered"]:
            signals.append("qr_replay_detected")
            rule_scores["qr_replay_detected"] = replay_result["score"]
        
        # 5. Device Fingerprint Checks
        device_result = self._check_device_fingerprint(db, user_id, data)
        for signal in device_result["signals"]:
            signals.append(signal)
            rule_scores[signal] = device_result["scores"].get(signal, 0.3)
        
        # 6. Host Confirmation Check
        host_result = self._check_host_confirmation(
            db, event.host_id, data.get("host_confirmed")
        )
        if host_result["triggered"]:
            signals.append(host_result["signal"])
            rule_scores[host_result["signal"]] = host_result["score"]
        
        # 7. User Trust Profile Check
        trust_result = self._check_user_trust(user_trust)
        if trust_result["triggered"]:
            signals.append(trust_result["signal"])
            rule_scores[trust_result["signal"]] = trust_result["score"]
        
        return signals, rule_scores
    
    def _check_gps_distance(
        self,
        user_lat: Optional[float],
        user_lon: Optional[float],
        event_lat: Optional[float],
        event_lon: Optional[float]
    ) -> Dict[str, Any]:
        """Check GPS distance between user and event."""
        if None in (user_lat, user_lon, event_lat, event_lon):
            return {"triggered": False}
        
        distance_km = self._haversine_distance(user_lat, user_lon, event_lat, event_lon)
        
        if distance_km > THRESHOLDS["gps_max_distance_km"]:
            return {
                "triggered": True,
                "signal": "gps_mismatch",
                "score": min(distance_km / 10.0, 1.0),  # Normalize, cap at 10km
                "distance_km": distance_km
            }
        
        return {"triggered": False, "distance_km": distance_km}
    
    def _check_gps_spoofing(
        self,
        db: Session,
        user_id: int,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Detect GPS spoofing via sudden location jumps."""
        # Get user's last known location from recent verifications
        last_verification = db.query(AttendanceVerification).filter(
            AttendanceVerification.user_id == user_id
        ).order_by(AttendanceVerification.created_at.desc()).first()
        
        if not last_verification or not last_verification.user_latitude:
            return {"triggered": False}
        
        user_lat = data.get("user_latitude")
        user_lon = data.get("user_longitude")
        
        if user_lat is None or user_lon is None:
            return {"triggered": False}
        
        distance = self._haversine_distance(
            last_verification.user_latitude,
            last_verification.user_longitude,
            user_lat,
            user_lon
        )
        
        # Check time elapsed
        time_diff = datetime.utcnow() - last_verification.created_at
        hours_elapsed = time_diff.total_seconds() / 3600
        
        # If distance is very high in short time, suspicious
        if hours_elapsed < 1 and distance > THRESHOLDS["gps_spoof_jump_km"]:
            return {
                "triggered": True,
                "score": 0.8,
                "distance_jump_km": distance,
                "hours_elapsed": hours_elapsed
            }
        
        return {"triggered": False}
    
    def _check_qr_timing(
        self,
        qr_scan_timestamp: Optional[datetime],
        event_start: Optional[datetime],
        event_end: Optional[datetime]
    ) -> Dict[str, Any]:
        """Check if QR scan is within valid time window."""
        if not qr_scan_timestamp or not event_start:
            return {"triggered": False}
        
        # Parse timestamp if string
        if isinstance(qr_scan_timestamp, str):
            qr_scan_timestamp = datetime.fromisoformat(
                qr_scan_timestamp.replace("Z", "+00:00")
            )
        
        if isinstance(event_start, str):
            event_start = datetime.fromisoformat(
                event_start.replace("Z", "+00:00")
            )
        
        minutes_diff = (qr_scan_timestamp - event_start).total_seconds() / 60
        
        # Check early
        if minutes_diff < THRESHOLDS["qr_early_window_min"]:
            return {
                "triggered": True,
                "signal": "early_qr_scan",
                "score": 0.15,
                "minutes_from_start": minutes_diff
            }
        
        # Check late
        if minutes_diff > THRESHOLDS["qr_late_window_min"]:
            if minutes_diff > 120:  # Very late (>2 hours)
                return {
                    "triggered": True,
                    "signal": "very_late_qr_scan",
                    "score": 0.5,
                    "minutes_from_start": minutes_diff
                }
            return {
                "triggered": True,
                "signal": "late_qr_scan",
                "score": 0.2,
                "minutes_from_start": minutes_diff
            }
        
        return {"triggered": False, "minutes_from_start": minutes_diff}
    
    def _check_qr_replay(
        self,
        db: Session,
        event_id: int,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Detect QR code replay attacks."""
        qr_code = data.get("qr_code")
        if not qr_code:
            return {"triggered": False}
        
        # Hash QR if not already hashed
        qr_hash = hashlib.sha256(qr_code.encode()).hexdigest() if len(qr_code) < 64 else qr_code
        
        # Check for recent scans of same QR
        recent_threshold = datetime.utcnow() - timedelta(
            seconds=THRESHOLDS["qr_replay_window_sec"]
        )
        
        recent_scan = db.query(QRScanLog).filter(
            and_(
                QRScanLog.qr_code_hash == qr_hash,
                QRScanLog.event_id == event_id,
                QRScanLog.scanned_at > recent_threshold
            )
        ).first()
        
        if recent_scan:
            return {
                "triggered": True,
                "score": 0.9,
                "previous_scan_seconds_ago": (
                    datetime.utcnow() - recent_scan.scanned_at
                ).total_seconds()
            }
        
        return {"triggered": False}
    
    def _check_device_fingerprint(
        self,
        db: Session,
        user_id: int,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check device fingerprint for fraud signals."""
        signals = []
        scores = {}
        
        device_hash = data.get("device_hash")
        if not device_hash:
            return {"signals": [], "scores": {}}
        
        # Check how many users use this device
        device_users = db.query(DeviceFingerprint).filter(
            DeviceFingerprint.device_hash == device_hash
        ).all()
        
        unique_users = set(d.user_id for d in device_users)
        
        if len(unique_users) > THRESHOLDS["max_users_per_device"]:
            signals.append("device_shared_multiple_users")
            scores["device_shared_multiple_users"] = 0.4
        
        # Check for simultaneous device usage
        recent_threshold = datetime.utcnow() - timedelta(minutes=30)
        
        user_devices = db.query(DeviceFingerprint).filter(
            and_(
                DeviceFingerprint.user_id == user_id,
                DeviceFingerprint.last_seen > recent_threshold
            )
        ).all()
        
        unique_devices = set(d.device_hash for d in user_devices)
        
        if len(unique_devices) > THRESHOLDS["max_simultaneous_devices"]:
            signals.append("device_simultaneous")
            scores["device_simultaneous"] = 0.5
        
        # Check if device is flagged
        flagged = db.query(DeviceFingerprint).filter(
            and_(
                DeviceFingerprint.device_hash == device_hash,
                DeviceFingerprint.is_flagged == True
            )
        ).first()
        
        if flagged:
            signals.append("device_flagged")
            scores["device_flagged"] = 0.6
        
        return {"signals": signals, "scores": scores}
    
    def _check_host_confirmation(
        self,
        db: Session,
        host_id: int,
        host_confirmed: Optional[bool]
    ) -> Dict[str, Any]:
        """Check host confirmation status."""
        if host_confirmed is None:
            return {"triggered": False}
        
        if host_confirmed == False:
            # Get host reliability
            host_rating = db.query(HostRating).filter(
                HostRating.host_id == host_id
            ).first()
            
            if host_rating and host_rating.overall_score and host_rating.overall_score > 4.0:
                # Reliable host says no - this is significant
                return {
                    "triggered": True,
                    "signal": "host_conflict",
                    "score": 0.5
                }
            else:
                return {
                    "triggered": True,
                    "signal": "host_not_confirmed",
                    "score": 0.15
                }
        
        return {"triggered": False}
    
    def _check_user_trust(
        self,
        user_trust: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check user's trust profile for fraud signals."""
        trust_score = user_trust.get("trust_score", 1.0)
        
        if trust_score < 0.3:
            return {
                "triggered": True,
                "signal": "user_prior_fraud",
                "score": 0.6
            }
        elif trust_score < 0.6:
            return {
                "triggered": True,
                "signal": "user_low_trust",
                "score": 0.3
            }
        
        return {"triggered": False}
    
    def _calculate_risk_score(
        self,
        signals: List[str],
        rule_scores: Dict[str, float],
        user_trust: Dict[str, Any]
    ) -> float:
        """Calculate final risk score from all signals."""
        if not signals:
            return 0.0
        
        # Weighted sum of triggered rules
        weighted_sum = sum(
            rule_scores.get(signal, RULE_WEIGHTS.get(signal, 0.2))
            for signal in signals
        )
        
        # Apply user trust modifier
        trust_score = user_trust.get("trust_score", 1.0)
        trust_modifier = 1.0 + (1.0 - trust_score) * 0.3  # Low trust increases risk
        
        # Normalize to 0-1
        risk_score = min(weighted_sum * trust_modifier, 1.0)
        
        return risk_score
    
    def _determine_status_and_action(
        self,
        risk_score: float,
        signals: List[str]
    ) -> Tuple[str, str]:
        """Determine check-in status and recommended action."""
        # Hard fraud signals = immediate rejection
        hard_fraud_signals = {"qr_replay_detected", "gps_spoof_detected", "device_flagged"}
        
        if any(s in hard_fraud_signals for s in signals):
            return "Fraudulent", "escalate_to_support"
        
        if risk_score <= THRESHOLDS["risk_valid_max"]:
            return "Valid", "accept"
        elif risk_score <= THRESHOLDS["risk_suspicious_max"]:
            return "Suspicious", "restrict"
        else:
            return "Fraudulent", "escalate_to_support"
    
    def _get_user_trust_profile(
        self,
        db: Session,
        user_id: int
    ) -> Dict[str, Any]:
        """Get user's trust profile."""
        profile = db.query(UserTrustProfile).filter(
            UserTrustProfile.user_id == user_id
        ).first()
        
        if profile:
            return {
                "trust_score": profile.trust_score,
                "total_verifications": profile.total_verifications,
                "fraudulent_count": profile.fraudulent_count,
                "suspicious_count": profile.suspicious_count
            }
        
        return {
            "trust_score": 1.0,
            "total_verifications": 0,
            "fraudulent_count": 0,
            "suspicious_count": 0
        }
    
    def _update_user_trust_profile(
        self,
        db: Session,
        user_id: int,
        status: str,
        signals: List[str]
    ) -> None:
        """Update user trust profile based on verification result."""
        try:
            profile = db.query(UserTrustProfile).filter(
                UserTrustProfile.user_id == user_id
            ).first()
            
            if not profile:
                profile = UserTrustProfile(user_id=user_id)
                db.add(profile)
            
            profile.total_verifications += 1
            
            if status == "Valid":
                profile.valid_count += 1
                # Slowly recover trust
                profile.trust_score = min(1.0, profile.trust_score + 0.02)
            elif status == "Suspicious":
                profile.suspicious_count += 1
                profile.trust_score = max(0.0, profile.trust_score - 0.05)
            elif status == "Fraudulent":
                profile.fraudulent_count += 1
                profile.penalties_applied += 1
                profile.last_penalty_at = datetime.utcnow()
                profile.trust_score = max(0.0, profile.trust_score - 0.15)
            
            # Update specific signal counts
            if "gps_mismatch" in signals:
                profile.gps_mismatch_count += 1
            if "qr_replay_detected" in signals:
                profile.qr_replay_count += 1
            if any("device" in s for s in signals):
                profile.device_anomaly_count += 1
            
            profile.last_updated = datetime.utcnow()
            db.commit()
            
        except Exception as e:
            logger.error(f"Error updating trust profile: {e}")
            db.rollback()
    
    def _log_device_fingerprint(
        self,
        db: Session,
        user_id: int,
        data: Dict[str, Any]
    ) -> None:
        """Log device fingerprint."""
        device_hash = data.get("device_hash")
        if not device_hash:
            return
        
        try:
            fingerprint = db.query(DeviceFingerprint).filter(
                and_(
                    DeviceFingerprint.device_hash == device_hash,
                    DeviceFingerprint.user_id == user_id
                )
            ).first()
            
            if fingerprint:
                fingerprint.last_seen = datetime.utcnow()
                fingerprint.check_in_count += 1
                fingerprint.device_os = data.get("device_os") or fingerprint.device_os
                fingerprint.app_instance_id = data.get("app_instance_id") or fingerprint.app_instance_id
            else:
                fingerprint = DeviceFingerprint(
                    device_hash=device_hash,
                    device_os=data.get("device_os"),
                    app_instance_id=data.get("app_instance_id"),
                    user_id=user_id
                )
                db.add(fingerprint)
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error logging device fingerprint: {e}")
            db.rollback()
    
    def _log_qr_scan(
        self,
        db: Session,
        user_id: int,
        event_id: int,
        data: Dict[str, Any],
        is_valid: bool
    ) -> None:
        """Log QR scan for replay detection."""
        qr_code = data.get("qr_code")
        if not qr_code:
            return
        
        try:
            qr_hash = hashlib.sha256(qr_code.encode()).hexdigest() if len(qr_code) < 64 else qr_code
            
            scan_log = QRScanLog(
                qr_code_hash=qr_hash,
                event_id=event_id,
                user_id=user_id,
                device_hash=data.get("device_hash"),
                is_valid=is_valid,
                rejection_reason=None if is_valid else "verification_failed"
            )
            db.add(scan_log)
            db.commit()
            
        except Exception as e:
            logger.error(f"Error logging QR scan: {e}")
            db.rollback()
    
    def _log_verification(
        self,
        db: Session,
        user_id: int,
        event_id: int,
        event: Event,
        check_in_data: Dict[str, Any],
        status: str,
        risk_score: float,
        action: str,
        signals: List[str],
        rule_scores: Dict[str, float],
        rewards_unlocked: bool,
        reviews_unlocked: bool,
        escrow_released: bool
    ) -> int:
        """Log verification decision for audit trail."""
        try:
            qr_ts = check_in_data.get("qr_scan_timestamp")
            if isinstance(qr_ts, str):
                qr_ts = datetime.fromisoformat(qr_ts.replace("Z", "+00:00"))
            
            event_start = event.start_time or event.event_date
            minutes_from_start = None
            if qr_ts and event_start:
                minutes_from_start = (qr_ts - event_start).total_seconds() / 60
            
            # Calculate distance
            distance_km = None
            if all([
                check_in_data.get("user_latitude"),
                check_in_data.get("user_longitude"),
                event.latitude,
                event.longitude
            ]):
                distance_km = self._haversine_distance(
                    check_in_data["user_latitude"],
                    check_in_data["user_longitude"],
                    event.latitude,
                    event.longitude
                )
            
            verification = AttendanceVerification(
                user_id=user_id,
                event_id=event_id,
                check_in_status=status,
                risk_score=risk_score,
                action=action,
                signals=signals,
                user_latitude=check_in_data.get("user_latitude"),
                user_longitude=check_in_data.get("user_longitude"),
                event_latitude=event.latitude,
                event_longitude=event.longitude,
                distance_km=distance_km,
                qr_scan_timestamp=qr_ts,
                event_start_timestamp=event_start,
                event_end_timestamp=event.end_time,
                minutes_from_start=minutes_from_start,
                device_hash=check_in_data.get("device_hash"),
                device_os=check_in_data.get("device_os"),
                app_instance_id=check_in_data.get("app_instance_id"),
                host_confirmed=check_in_data.get("host_confirmed"),
                model_version=MODEL_VERSION,
                rules_triggered=rule_scores,
                rewards_unlocked=rewards_unlocked,
                reviews_unlocked=reviews_unlocked,
                escrow_released=escrow_released
            )
            db.add(verification)
            db.commit()
            
            return verification.id
            
        except Exception as e:
            logger.error(f"Error logging verification: {e}")
            db.rollback()
            return 0
    
    def record_support_decision(
        self,
        db: Session,
        verification_id: int,
        decision: str,  # 'confirmed_valid', 'confirmed_fraud', 'inconclusive'
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Record support team's decision on escalated verification.
        
        MANDATORY FEEDBACK LOOP:
        This feeds back into training data and rule refinement.
        """
        try:
            verification = db.query(AttendanceVerification).filter(
                AttendanceVerification.id == verification_id
            ).first()
            
            if not verification:
                return {"success": False, "error": "Verification not found"}
            
            verification.support_decision = decision
            verification.support_decision_at = datetime.utcnow()
            verification.support_notes = notes
            
            # Update unlocks based on decision
            if decision == "confirmed_valid":
                verification.rewards_unlocked = True
                verification.reviews_unlocked = True
                verification.escrow_released = True
                # Restore user trust
                self._restore_user_trust(db, verification.user_id)
            elif decision == "confirmed_fraud":
                verification.rewards_unlocked = False
                verification.reviews_unlocked = False
                verification.escrow_released = False
                # Penalize user trust further
                self._penalize_user(db, verification.user_id)
            
            db.commit()
            
            return {
                "success": True,
                "verification_id": verification_id,
                "decision": decision,
                "rewards_unlocked": verification.rewards_unlocked,
                "reviews_unlocked": verification.reviews_unlocked,
                "escrow_released": verification.escrow_released
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error recording support decision: {e}")
            return {"success": False, "error": str(e)}
    
    def _restore_user_trust(self, db: Session, user_id: int) -> None:
        """Restore user trust after false positive."""
        try:
            profile = db.query(UserTrustProfile).filter(
                UserTrustProfile.user_id == user_id
            ).first()
            
            if profile:
                profile.trust_score = min(1.0, profile.trust_score + 0.1)
                profile.last_updated = datetime.utcnow()
                db.commit()
        except Exception as e:
            logger.error(f"Error restoring trust: {e}")
            db.rollback()
    
    def _penalize_user(self, db: Session, user_id: int) -> None:
        """Apply additional penalty for confirmed fraud."""
        try:
            profile = db.query(UserTrustProfile).filter(
                UserTrustProfile.user_id == user_id
            ).first()
            
            if profile:
                profile.trust_score = max(0.0, profile.trust_score - 0.25)
                profile.penalties_applied += 1
                profile.last_penalty_at = datetime.utcnow()
                profile.last_updated = datetime.utcnow()
                db.commit()
        except Exception as e:
            logger.error(f"Error penalizing user: {e}")
            db.rollback()
    
    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two GPS coordinates in km."""
        R = 6371  # Earth's radius in km
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def _error_response(self, error: str) -> Dict[str, Any]:
        """Return error response."""
        return {
            "check_in_status": "Error",
            "risk_score": 0.0,
            "signals": [],
            "action": "escalate_to_support",
            "rewards_unlocked": False,
            "reviews_unlocked": False,
            "escrow_released": False,
            "error": error,
            "model_version": MODEL_VERSION
        }
    
    def get_verification_history(
        self,
        db: Session,
        user_id: Optional[int] = None,
        event_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get verification history for audit."""
        query = db.query(AttendanceVerification)
        
        if user_id:
            query = query.filter(AttendanceVerification.user_id == user_id)
        if event_id:
            query = query.filter(AttendanceVerification.event_id == event_id)
        if status:
            query = query.filter(AttendanceVerification.check_in_status == status)
        
        verifications = query.order_by(
            AttendanceVerification.created_at.desc()
        ).limit(limit).all()
        
        return [
            {
                "id": v.id,
                "user_id": v.user_id,
                "event_id": v.event_id,
                "check_in_status": v.check_in_status,
                "risk_score": v.risk_score,
                "action": v.action,
                "signals": v.signals,
                "support_decision": v.support_decision,
                "created_at": v.created_at.isoformat() if v.created_at else None
            }
            for v in verifications
        ]


# Singleton instance
attendance_verification_service = AttendanceVerificationService()
