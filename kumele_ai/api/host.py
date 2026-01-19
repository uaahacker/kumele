"""
Host Router - Host rating endpoints
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from kumele_ai.dependencies import get_db
from kumele_ai.services.host_service import host_service

router = APIRouter()


@router.get("/{host_id}/rating")
async def get_host_rating(
    host_id: int,
    db: Session = Depends(get_db)
):
    """
    Get aggregated host score with detailed breakdown.
    
    Weighted Host Rating Model:
    
    A) Attendee Ratings = 70% (only from attendees)
       - Communication & Responsiveness (20%)
       - Respect (20%)
       - Professionalism (20%)
       - Event Atmosphere (5%)
       - Value for Money - if paid (5%)
    
    B) System Reliability = 30% (automatic)
       - Event Completion Ratio (15%)
       - Attendance Follow-Through (10%)
       - Repeat Attendee Ratio (5%)
    
    Final Formula:
    Host Score (0-100) = (0.7 × Attendee Rating %) + (0.3 × Reliability %)
    """
    result = host_service.calculate_host_rating(
        db=db,
        host_id=host_id
    )
    
    return result
