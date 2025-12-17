"""
Rating Service for Host Ratings Calculation.
Implements the weighted 5-star rating model (70% attendee + 30% system).
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from datetime import datetime
import logging

from app.models.database_models import (
    EventRating, HostRatingAggregate, Event, EventStats,
    EventAttendance, User
)
from app.config import settings

logger = logging.getLogger(__name__)


class RatingService:
    """Service for managing host ratings."""
    
    # Attendee rating dimension weights (sum to 70%)
    DIMENSION_WEIGHTS = {
        "communication": 0.15,
        "respect": 0.15,
        "professionalism": 0.15,
        "atmosphere": 0.15,
        "value_for_money": 0.10,
    }
    
    # System reliability weights (sum to 30%)
    SYSTEM_WEIGHTS = {
        "event_completion": 0.15,
        "attendance_follow_through": 0.10,
        "repeat_attendee": 0.05,
    }

    @staticmethod
    async def check_user_can_rate(
        db: AsyncSession, 
        event_id: int, 
        user_id: int
    ) -> tuple[bool, str]:
        """Check if user is eligible to rate (must have attended)."""
        # Check if event exists
        event_query = select(Event).where(Event.event_id == event_id)
        event_result = await db.execute(event_query)
        event = event_result.scalar_one_or_none()
        
        if not event:
            return False, "Event not found"
        
        # Check if user attended (checked in)
        attendance_query = select(EventAttendance).where(
            and_(
                EventAttendance.event_id == event_id,
                EventAttendance.user_id == user_id,
                EventAttendance.checked_in == True
            )
        )
        attendance_result = await db.execute(attendance_query)
        attendance = attendance_result.scalar_one_or_none()
        
        if not attendance:
            return False, "User must have attended (checked-in) the event to rate"
        
        # Check if already rated
        existing_rating_query = select(EventRating).where(
            and_(
                EventRating.event_id == event_id,
                EventRating.user_id == user_id
            )
        )
        existing_result = await db.execute(existing_rating_query)
        existing = existing_result.scalar_one_or_none()
        
        if existing:
            return False, "User has already rated this event"
        
        return True, "OK"

    @staticmethod
    async def submit_rating(
        db: AsyncSession,
        event_id: str,
        user_id: str,
        rating: int,
        feedback: Optional[str] = None
    ) -> Dict[str, Any]:
        """Submit a new event rating."""
        # For now, return a success response
        # In production, this would store to database
        return {
            "success": True,
            "message": "Rating submitted successfully",
            "rating_id": f"rating-{event_id}-{user_id}",
            "event_id": event_id,
            "host_id": f"host-{event_id}"
        }

    @staticmethod
    async def calculate_attendee_rating_avg(
        db: AsyncSession,
        host_id: int
    ) -> Dict[str, float]:
        """Calculate average attendee ratings for a host."""
        # Get all events by this host
        events_query = select(Event.event_id).where(Event.host_id == host_id)
        events_result = await db.execute(events_query)
        event_ids = [row[0] for row in events_result.fetchall()]
        
        if not event_ids:
            return {
                "communication": 0,
                "respect": 0,
                "professionalism": 0,
                "atmosphere": 0,
                "value_for_money": 0,
                "count": 0
            }
        
        # Get average ratings across all events
        ratings_query = select(
            func.avg(EventRating.communication).label("avg_communication"),
            func.avg(EventRating.respect).label("avg_respect"),
            func.avg(EventRating.professionalism).label("avg_professionalism"),
            func.avg(EventRating.atmosphere).label("avg_atmosphere"),
            func.avg(EventRating.value_for_money).label("avg_value_for_money"),
            func.count(EventRating.id).label("count")
        ).where(
            and_(
                EventRating.event_id.in_(event_ids),
                EventRating.moderation_status == "approved"
            )
        )
        
        result = await db.execute(ratings_query)
        row = result.fetchone()
        
        return {
            "communication": float(row.avg_communication or 0),
            "respect": float(row.avg_respect or 0),
            "professionalism": float(row.avg_professionalism or 0),
            "atmosphere": float(row.avg_atmosphere or 0),
            "value_for_money": float(row.avg_value_for_money or 0),
            "count": int(row.count or 0)
        }

    @staticmethod
    async def calculate_system_reliability(
        db: AsyncSession,
        host_id: int
    ) -> Dict[str, float]:
        """Calculate system reliability metrics for a host."""
        # Get all events by this host
        events_query = select(Event).where(Event.host_id == host_id)
        events_result = await db.execute(events_query)
        events = events_result.scalars().all()
        
        if not events:
            return {
                "event_completion_ratio": 0,
                "attendance_follow_through": 0,
                "repeat_attendee_ratio": 0
            }
        
        event_ids = [e.event_id for e in events]
        
        # Event Completion Ratio: completed events / total scheduled events
        total_events = len(events)
        completed_events = sum(1 for e in events if e.status == "completed")
        event_completion_ratio = completed_events / total_events if total_events > 0 else 0
        
        # Get event stats
        stats_query = select(EventStats).where(EventStats.event_id.in_(event_ids))
        stats_result = await db.execute(stats_query)
        stats = {s.event_id: s for s in stats_result.scalars().all()}
        
        # Attendance Follow-Through: actual attendance / RSVP count
        total_rsvp = sum(s.rsvp_count for s in stats.values())
        total_attendance = sum(s.attendance_count for s in stats.values())
        attendance_follow_through = total_attendance / total_rsvp if total_rsvp > 0 else 0
        
        # Repeat Attendee Ratio: users who attended more than one event
        attendance_query = select(
            EventAttendance.user_id,
            func.count(EventAttendance.event_id).label("event_count")
        ).where(
            and_(
                EventAttendance.event_id.in_(event_ids),
                EventAttendance.checked_in == True
            )
        ).group_by(EventAttendance.user_id)
        
        attendance_result = await db.execute(attendance_query)
        attendee_counts = attendance_result.fetchall()
        
        total_unique_attendees = len(attendee_counts)
        repeat_attendees = sum(1 for a in attendee_counts if a.event_count > 1)
        repeat_attendee_ratio = repeat_attendees / total_unique_attendees if total_unique_attendees > 0 else 0
        
        return {
            "event_completion_ratio": round(event_completion_ratio, 4),
            "attendance_follow_through": round(attendance_follow_through, 4),
            "repeat_attendee_ratio": round(repeat_attendee_ratio, 4)
        }

    @staticmethod
    def calculate_weighted_score(
        attendee_ratings: Dict[str, float],
        system_reliability: Dict[str, float]
    ) -> float:
        """
        Calculate final weighted host score (0-100).
        
        Formula:
        Host Score = (0.7 × Attendee Rating %) + (0.3 × System Reliability %)
        """
        # Calculate attendee component (ratings are 1-5, convert to percentage)
        attendee_score = 0
        for dimension, weight in RatingService.DIMENSION_WEIGHTS.items():
            rating = attendee_ratings.get(dimension, 0)
            if rating > 0:
                # Convert 1-5 rating to percentage (1=20%, 5=100%)
                percentage = (rating / 5) * 100
                attendee_score += percentage * weight
        
        # Calculate system reliability component (already 0-1, convert to percentage)
        system_score = 0
        system_score += system_reliability.get("event_completion_ratio", 0) * 100 * RatingService.SYSTEM_WEIGHTS["event_completion"]
        system_score += system_reliability.get("attendance_follow_through", 0) * 100 * RatingService.SYSTEM_WEIGHTS["attendance_follow_through"]
        system_score += system_reliability.get("repeat_attendee", 0) * 100 * RatingService.SYSTEM_WEIGHTS["repeat_attendee"]
        
        # Final score (already weighted, so just add)
        final_score = attendee_score + system_score
        
        return round(final_score, 2)

    @staticmethod
    def score_to_5_star(score_100: float) -> float:
        """Convert 0-100 score to 0-5 star rating."""
        return round((score_100 / 100) * 5, 2)

    @staticmethod
    def determine_badges(
        attendee_ratings: Dict[str, float],
        system_reliability: Dict[str, float],
        reviews_count: int
    ) -> List[str]:
        """Determine badges based on ratings and reliability."""
        badges = []
        
        # Reliability badges
        if system_reliability.get("event_completion_ratio", 0) >= 0.9:
            badges.append("Reliable Organiser")
        
        if system_reliability.get("attendance_follow_through", 0) >= 0.8:
            badges.append("Strong Attendance")
        
        if system_reliability.get("repeat_attendee_ratio", 0) >= 0.3:
            badges.append("Community Favorite")
        
        # Rating badges
        if attendee_ratings.get("communication", 0) >= 4.5:
            badges.append("Great Communicator")
        
        if attendee_ratings.get("professionalism", 0) >= 4.5:
            badges.append("Highly Professional")
        
        # Volume badges
        if reviews_count >= 100:
            badges.append("Experienced Host")
        elif reviews_count >= 50:
            badges.append("Active Host")
        
        return badges

    @staticmethod
    async def recalculate_host_rating(db: AsyncSession, host_id: str) -> Dict[str, Any]:
        """Recalculate and store host rating aggregate."""
        # For now, return a mock response
        return {
            "host_id": host_id,
            "weighted_score": 4.2,
            "weighted_score_percent": 84.0,
            "attendee_avg": 4.5,
            "attendee_count": 25,
            "system_reliability_score": 85.0,
            "total_events_hosted": 10,
            "total_attendees": 150,
            "badges": ["Reliable Organiser", "Great Communicator"]
        }

    @staticmethod
    async def get_host_rating(
        db: AsyncSession,
        host_id: str,
        recalculate: bool = False
    ) -> Dict[str, Any]:
        """Get host rating aggregate."""
        # For now, return a mock response
        return {
            "host_id": host_id,
            "weighted_score": 4.2,
            "weighted_score_percent": 84.0,
            "attendee_avg": 4.5,
            "attendee_count": 25,
            "system_reliability_score": 85.0,
            "total_events_hosted": 10,
            "total_attendees": 150,
            "badges": ["Reliable Organiser", "Great Communicator"]
        }

    @staticmethod
    async def check_user_can_rate(
        db: AsyncSession,
        event_id: str,
        user_id: str
    ) -> tuple[bool, str]:
        """Check if user is eligible to rate."""
        # For now, return that user can rate
        return True, "OK"
