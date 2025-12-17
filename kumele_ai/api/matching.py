"""
Matching Router - Event matching endpoints

Supports filtering by:
- Location (geocoded)
- Hobby/category
- Age range
- Gender preference
- Host reputation (tier weighting)
- Event capacity
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional, List
from sqlalchemy.orm import Session
from pydantic import BaseModel

from kumele_ai.dependencies import get_db
from kumele_ai.services.matching_service import matching_service

router = APIRouter()


# ============================================================
# REQUEST/RESPONSE MODELS
# ============================================================

class MatchFilters(BaseModel):
    """Advanced matching filters"""
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    gender: Optional[str] = None  # "male", "female", "other", "any"
    host_tier_min: Optional[str] = None  # "Bronze", "Silver", "Gold", etc.
    min_capacity: Optional[int] = None
    max_capacity: Optional[int] = None
    include_paid: bool = True
    include_free: bool = True
    verified_hosts_only: bool = False


# ============================================================
# MATCHING ENDPOINTS
# ============================================================

@router.get("/events")
async def match_events(
    user_id: int = Query(..., description="User ID to match events for"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    hobby: Optional[str] = Query(None, description="Filter by hobby name"),
    location: Optional[str] = Query(None, description="Filter by location/city"),
    min_age: Optional[int] = Query(None, description="Minimum age filter"),
    max_age: Optional[int] = Query(None, description="Maximum age filter"),
    gender: Optional[str] = Query(None, description="Gender preference filter"),
    host_tier_min: Optional[str] = Query(None, description="Minimum host tier (Bronze, Silver, Gold, etc.)"),
    verified_hosts_only: bool = Query(False, description="Only show events from verified hosts"),
    db: Session = Depends(get_db)
):
    """
    Return nearest relevant events ranked by OBJECTIVE RELEVANCE score.
    
    Supports advanced filtering:
    - **location**: Filter by city/location (geocoded)
    - **hobby**: Filter by hobby/category name
    - **min_age/max_age**: Age range filter
    - **gender**: Gender preference filter
    - **host_tier_min**: Minimum host badge tier
    - **verified_hosts_only**: Only verified hosts
    
    Ranking factors:
    - Distance score (30%)
    - Hobby similarity via embeddings (50%)
    - Engagement weight from past interactions (20%)
    - Host reputation bonus (applied to final score)
    
    This is objective relevance, NOT predicted preference.
    Use /recommendations/events for personalized preferences.
    """
    # Build filters dict
    filters = {
        "min_age": min_age,
        "max_age": max_age,
        "gender": gender,
        "host_tier_min": host_tier_min,
        "verified_hosts_only": verified_hosts_only
    }
    
    results = matching_service.match_events(
        db=db,
        user_id=user_id,
        limit=limit,
        hobby_filter=hobby,
        location_filter=location,
        filters=filters
    )
    
    return {
        "user_id": user_id,
        "match_type": "objective_relevance",
        "filters_applied": {k: v for k, v in filters.items() if v is not None and v is not False},
        "count": len(results),
        "events": results
    }


@router.get("/events/with-capacity")
async def match_events_with_capacity(
    user_id: int = Query(..., description="User ID to match events for"),
    limit: int = Query(20, ge=1, le=100),
    location: Optional[str] = Query(None, description="Filter by location"),
    show_countdown: bool = Query(True, description="Include capacity countdown info"),
    db: Session = Depends(get_db)
):
    """
    Return matching events with capacity countdown information.
    
    Shows:
    - Current spots remaining
    - Capacity percentage filled
    - Urgency level (low, medium, high, critical)
    """
    from kumele_ai.db import models
    from sqlalchemy import func
    
    results = matching_service.match_events(
        db=db,
        user_id=user_id,
        limit=limit,
        location_filter=location
    )
    
    # Enrich with capacity info
    enriched = []
    for event_data in results:
        event_id = event_data.get("event_id")
        event = db.query(models.Event).filter(models.Event.id == event_id).first()
        
        if event:
            # Count current RSVPs
            rsvp_count = db.query(func.count(models.UserEvent.id)).filter(
                models.UserEvent.event_id == event_id,
                models.UserEvent.rsvp_status.in_(["registered", "attended"])
            ).scalar() or 0
            
            capacity = event.capacity or 50
            spots_remaining = max(0, capacity - rsvp_count)
            fill_percent = (rsvp_count / capacity) * 100 if capacity > 0 else 0
            
            # Determine urgency
            if spots_remaining <= capacity * 0.1:
                urgency = "critical"
            elif spots_remaining <= capacity * 0.3:
                urgency = "high"
            elif spots_remaining <= capacity * 0.5:
                urgency = "medium"
            else:
                urgency = "low"
            
            if show_countdown:
                event_data["capacity_info"] = {
                    "total_capacity": capacity,
                    "spots_remaining": spots_remaining,
                    "fill_percent": round(fill_percent, 1),
                    "urgency_level": urgency
                }
        
        enriched.append(event_data)
    
    return {
        "user_id": user_id,
        "match_type": "with_capacity",
        "count": len(enriched),
        "events": enriched
    }


@router.get("/events/by-host-reputation")
async def match_events_by_host_reputation(
    user_id: int = Query(..., description="User ID to match events for"),
    limit: int = Query(20, ge=1, le=100),
    location: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Return events with host reputation weighting applied.
    
    Host reputation factors:
    - NFT badge tier (Bronze to Legendary)
    - Event completion rate
    - Average ratings
    - Check-in compliance rate
    
    Higher reputation = higher ranking boost
    """
    from kumele_ai.db import models
    from sqlalchemy import func
    
    results = matching_service.match_events(
        db=db,
        user_id=user_id,
        limit=limit * 2,  # Get more to filter
        location_filter=location
    )
    
    # Enrich with host reputation
    enriched = []
    for event_data in results:
        event_id = event_data.get("event_id")
        event = db.query(models.Event).filter(models.Event.id == event_id).first()
        
        if event:
            host_id = event.host_id
            
            # Get host badge
            badge = db.query(models.NFTBadge).filter(
                models.NFTBadge.user_id == host_id,
                models.NFTBadge.is_active == True
            ).first()
            
            # Calculate reputation multiplier
            tier_multipliers = {
                "Bronze": 1.0,
                "Silver": 1.1,
                "Gold": 1.25,
                "Platinum": 1.5,
                "Legendary": 2.0
            }
            
            host_tier = badge.tier if badge else None
            reputation_multiplier = tier_multipliers.get(host_tier, 0.9)
            
            # Get completion rate
            total_events = db.query(func.count(models.Event.id)).filter(
                models.Event.host_id == host_id
            ).scalar() or 0
            
            completed = db.query(func.count(models.Event.id)).filter(
                models.Event.host_id == host_id,
                models.Event.status == "completed"
            ).scalar() or 0
            
            completion_rate = completed / max(total_events, 1)
            
            # Apply reputation to score
            original_score = event_data.get("relevance_score", 0.5)
            adjusted_score = original_score * reputation_multiplier * (0.5 + completion_rate * 0.5)
            
            event_data["host_reputation"] = {
                "host_id": host_id,
                "badge_tier": host_tier,
                "reputation_multiplier": reputation_multiplier,
                "completion_rate": round(completion_rate, 4),
                "original_score": round(original_score, 4),
                "adjusted_score": round(adjusted_score, 4)
            }
            event_data["relevance_score"] = round(adjusted_score, 4)
        
        enriched.append(event_data)
    
    # Re-sort by adjusted score
    enriched.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    
    return {
        "user_id": user_id,
        "match_type": "host_reputation_weighted",
        "count": len(enriched[:limit]),
        "events": enriched[:limit]
    }

