"""
Event Service - Handles event rating and related operations
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from kumele_ai.db.models import Event, UserEvent, EventRating
from kumele_ai.services.moderation_service import moderation_service

logger = logging.getLogger(__name__)


class EventService:
    """Service for event operations"""
    
    def submit_rating(
        self,
        db: Session,
        event_id: int,
        user_id: int,
        rating: float,
        communication_score: Optional[float] = None,
        respect_score: Optional[float] = None,
        professionalism_score: Optional[float] = None,
        atmosphere_score: Optional[float] = None,
        value_score: Optional[float] = None,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """Submit a rating for an event"""
        try:
            # Verify event exists
            event = db.query(Event).filter(Event.id == event_id).first()
            if not event:
                return {"success": False, "error": "Event not found"}
            
            # Verify user was an attendee and checked in
            attendance = db.query(UserEvent).filter(
                and_(
                    UserEvent.event_id == event_id,
                    UserEvent.user_id == user_id
                )
            ).first()
            
            if not attendance:
                return {"success": False, "error": "User did not attend this event"}
            
            if not attendance.checked_in:
                return {"success": False, "error": "User must be checked in to rate"}
            
            # Check for existing rating
            existing_rating = db.query(EventRating).filter(
                and_(
                    EventRating.event_id == event_id,
                    EventRating.user_id == user_id
                )
            ).first()
            
            if existing_rating:
                return {"success": False, "error": "User has already rated this event"}
            
            # Moderate comment if provided
            moderation_status = "approved"
            if comment:
                mod_result = moderation_service.moderate_text(
                    db,
                    comment,
                    subtype="event_rating_comment",
                    content_id=f"rating_{event_id}_{user_id}"
                )
                
                if mod_result.get("decision") == "reject":
                    return {
                        "success": False,
                        "error": "Comment failed moderation",
                        "moderation_labels": mod_result.get("labels")
                    }
                
                moderation_status = "approved" if mod_result.get("decision") == "approve" else "pending_review"
            
            # Create rating
            event_rating = EventRating(
                event_id=event_id,
                user_id=user_id,
                rating=rating,
                communication_score=communication_score,
                respect_score=respect_score,
                professionalism_score=professionalism_score,
                atmosphere_score=atmosphere_score,
                value_score=value_score,
                comment=comment,
                moderation_status=moderation_status
            )
            
            db.add(event_rating)
            db.commit()
            db.refresh(event_rating)
            
            return {
                "success": True,
                "rating_id": event_rating.id,
                "moderation_status": moderation_status
            }
            
        except Exception as e:
            logger.error(f"Rating submission error: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
    
    def get_event_ratings(
        self,
        db: Session,
        event_id: int
    ) -> Dict[str, Any]:
        """Get all ratings for an event"""
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            return {"error": "Event not found"}
        
        ratings = db.query(EventRating).filter(
            EventRating.event_id == event_id,
            EventRating.moderation_status.in_(["approved", "pending_review"])
        ).all()
        
        if not ratings:
            return {
                "event_id": event_id,
                "rating_count": 0,
                "average_rating": None,
                "ratings": []
            }
        
        avg_rating = sum(r.rating for r in ratings) / len(ratings)
        
        return {
            "event_id": event_id,
            "rating_count": len(ratings),
            "average_rating": round(avg_rating, 2),
            "ratings": [
                {
                    "rating_id": r.id,
                    "rating": r.rating,
                    "communication": r.communication_score,
                    "respect": r.respect_score,
                    "professionalism": r.professionalism_score,
                    "atmosphere": r.atmosphere_score,
                    "value": r.value_score,
                    "comment": r.comment if r.moderation_status == "approved" else None,
                    "created_at": r.created_at.isoformat() if r.created_at else None
                }
                for r in ratings
            ]
        }


# Singleton instance
event_service = EventService()
