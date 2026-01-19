"""
Host Service - Handles host rating calculations
"""
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from kumele_ai.db.models import (
    User, Event, UserEvent, EventRating, HostRating
)

logger = logging.getLogger(__name__)


class HostService:
    """Service for host rating calculations"""
    
    # Weight configuration for host rating model
    WEIGHTS = {
        # Attendee Ratings (70% total)
        "communication": 0.20,
        "respect": 0.20,
        "professionalism": 0.20,
        "atmosphere": 0.05,
        "value": 0.05,
        # System Reliability (30% total)
        "completion_ratio": 0.15,
        "attendance_followthrough": 0.10,
        "repeat_attendee_ratio": 0.05
    }
    
    def calculate_host_rating(
        self,
        db: Session,
        host_id: int
    ) -> Dict[str, Any]:
        """Calculate comprehensive host rating"""
        try:
            # Get host
            host = db.query(User).filter(User.id == host_id).first()
            if not host:
                return {"error": "Host not found"}
            
            # Get all events hosted
            all_events = db.query(Event).filter(Event.host_id == host_id).all()
            total_events = len(all_events)
            
            if total_events == 0:
                return {
                    "host_id": host_id,
                    "overall_score": 0,
                    "total_events": 0,
                    "message": "No events hosted yet"
                }
            
            # Completed events
            completed_events = [e for e in all_events if e.status == "completed"]
            completed_count = len(completed_events)
            
            # Completion ratio
            completion_ratio = completed_count / total_events if total_events > 0 else 0
            
            # Get all ratings for this host's events
            event_ids = [e.id for e in completed_events]
            
            if not event_ids:
                return {
                    "host_id": host_id,
                    "overall_score": completion_ratio * 30,  # Only reliability component
                    "total_events": total_events,
                    "completed_events": 0,
                    "breakdown": {
                        "attendee_rating": None,
                        "reliability": {
                            "completion_ratio": round(completion_ratio * 100, 1)
                        }
                    }
                }
            
            # Aggregate attendee ratings
            ratings = db.query(EventRating).filter(
                EventRating.event_id.in_(event_ids)
            ).all()
            
            if not ratings:
                # No ratings yet, use defaults
                avg_communication = None
                avg_respect = None
                avg_professionalism = None
                avg_atmosphere = None
                avg_value = None
                attendee_rating_pct = 50  # Default
            else:
                # Calculate averages
                avg_communication = self._safe_avg([r.communication_score for r in ratings if r.communication_score])
                avg_respect = self._safe_avg([r.respect_score for r in ratings if r.respect_score])
                avg_professionalism = self._safe_avg([r.professionalism_score for r in ratings if r.professionalism_score])
                avg_atmosphere = self._safe_avg([r.atmosphere_score for r in ratings if r.atmosphere_score])
                avg_value = self._safe_avg([r.value_score for r in ratings if r.value_score])
                
                # Calculate attendee rating percentage (assuming 5-point scale)
                weighted_attendee = 0
                if avg_communication:
                    weighted_attendee += (avg_communication / 5) * self.WEIGHTS["communication"]
                if avg_respect:
                    weighted_attendee += (avg_respect / 5) * self.WEIGHTS["respect"]
                if avg_professionalism:
                    weighted_attendee += (avg_professionalism / 5) * self.WEIGHTS["professionalism"]
                if avg_atmosphere:
                    weighted_attendee += (avg_atmosphere / 5) * self.WEIGHTS["atmosphere"]
                if avg_value:
                    weighted_attendee += (avg_value / 5) * self.WEIGHTS["value"]
                
                # Normalize to 70%
                attendee_rating_pct = (weighted_attendee / 0.70) * 100 if weighted_attendee > 0 else 50
            
            # Attendance follow-through
            total_attendees = db.query(func.count(UserEvent.id)).filter(
                and_(
                    UserEvent.event_id.in_(event_ids),
                    UserEvent.checked_in == True
                )
            ).scalar() or 0
            
            total_registered = db.query(func.count(UserEvent.id)).filter(
                UserEvent.event_id.in_(event_ids)
            ).scalar() or 0
            
            followthrough_ratio = total_attendees / total_registered if total_registered > 0 else 0
            
            # Repeat attendee ratio
            attendee_counts = db.query(
                UserEvent.user_id,
                func.count(UserEvent.id).label("count")
            ).filter(
                and_(
                    UserEvent.event_id.in_(event_ids),
                    UserEvent.checked_in == True
                )
            ).group_by(UserEvent.user_id).all()
            
            unique_attendees = len(attendee_counts)
            repeat_attendees = sum(1 for _, count in attendee_counts if count > 1)
            repeat_ratio = repeat_attendees / unique_attendees if unique_attendees > 0 else 0
            
            # Calculate reliability score (30%)
            reliability_score = (
                completion_ratio * self.WEIGHTS["completion_ratio"] +
                followthrough_ratio * self.WEIGHTS["attendance_followthrough"] +
                repeat_ratio * self.WEIGHTS["repeat_attendee_ratio"]
            )
            reliability_pct = (reliability_score / 0.30) * 100
            
            # Final score: 0-100
            # Host Score = (0.7 × Attendee Rating %) + (0.3 × Reliability %)
            overall_score = (0.7 * attendee_rating_pct) + (0.3 * reliability_pct)
            
            # Update or create HostRating record
            host_rating = db.query(HostRating).filter(HostRating.host_id == host_id).first()
            if not host_rating:
                host_rating = HostRating(host_id=host_id)
                db.add(host_rating)
            
            host_rating.total_events = total_events
            host_rating.completed_events = completed_count
            host_rating.total_attendees = total_attendees
            host_rating.repeat_attendees = repeat_attendees
            host_rating.avg_communication = avg_communication
            host_rating.avg_respect = avg_respect
            host_rating.avg_professionalism = avg_professionalism
            host_rating.avg_atmosphere = avg_atmosphere
            host_rating.avg_value = avg_value
            host_rating.overall_score = overall_score
            
            db.commit()
            
            return {
                "host_id": host_id,
                "overall_score": round(overall_score, 1),
                "total_events": total_events,
                "completed_events": completed_count,
                "total_ratings": len(ratings),
                "breakdown": {
                    "attendee_rating": {
                        "score_pct": round(attendee_rating_pct, 1),
                        "weight": "70%",
                        "components": {
                            "communication": {"avg": round(avg_communication, 2) if avg_communication else None, "weight": "20%"},
                            "respect": {"avg": round(avg_respect, 2) if avg_respect else None, "weight": "20%"},
                            "professionalism": {"avg": round(avg_professionalism, 2) if avg_professionalism else None, "weight": "20%"},
                            "atmosphere": {"avg": round(avg_atmosphere, 2) if avg_atmosphere else None, "weight": "5%"},
                            "value": {"avg": round(avg_value, 2) if avg_value else None, "weight": "5%"}
                        }
                    },
                    "reliability": {
                        "score_pct": round(reliability_pct, 1),
                        "weight": "30%",
                        "components": {
                            "completion_ratio": {"value": round(completion_ratio * 100, 1), "weight": "15%"},
                            "attendance_followthrough": {"value": round(followthrough_ratio * 100, 1), "weight": "10%"},
                            "repeat_attendee_ratio": {"value": round(repeat_ratio * 100, 1), "weight": "5%"}
                        }
                    }
                },
                "unique_attendees": unique_attendees,
                "repeat_attendees": repeat_attendees
            }
            
        except Exception as e:
            logger.error(f"Host rating calculation error: {e}")
            return {"error": str(e)}
    
    def _safe_avg(self, values: list) -> Optional[float]:
        """Calculate average safely"""
        filtered = [v for v in values if v is not None]
        if not filtered:
            return None
        return sum(filtered) / len(filtered)


# Singleton instance
host_service = HostService()
