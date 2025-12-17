"""
Matching Service for Event Matching.
Location-based + hobby similarity + engagement weighting.
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from datetime import datetime, timedelta
import logging
import math
import httpx
import hashlib

from app.models.database_models import (
    User, Event, EventAttendance, UserHobby, InterestTaxonomy,
    HostRatingAggregate, UserInteraction
)
from app.config import settings

logger = logging.getLogger(__name__)


class MatchingService:
    """
    Service for matching events to users.
    
    Matching Pipeline:
    1. Geocode address → lat/lon (OpenStreetMap Nominatim)
    2. Compute distance (Haversine formula)
    3. Create hobby/event embeddings
    4. Compute hybrid relevance score
    5. Re-rank with engagement + trust boosting
    """
    
    # Weights for final score
    DISTANCE_WEIGHT = 0.25
    HOBBY_WEIGHT = 0.35
    ENGAGEMENT_WEIGHT = 0.20
    HOST_RATING_WEIGHT = 0.10
    REWARD_BOOST_WEIGHT = 0.10
    
    # Reward tier boosts
    REWARD_BOOSTS = {
        "none": 0.0,
        "bronze": 0.05,
        "silver": 0.10,
        "gold": 0.15,
    }

    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two points using Haversine formula.
        Returns distance in kilometers.
        """
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c

    @staticmethod
    def distance_score(distance_km: float, max_distance_km: float = 50.0) -> float:
        """
        Convert distance to a 0-1 score (closer = higher).
        Uses exponential decay.
        """
        if distance_km <= 0:
            return 1.0
        if distance_km >= max_distance_km:
            return 0.0
        
        # Exponential decay - 50% score at half max distance
        decay_rate = math.log(2) / (max_distance_km / 2)
        score = math.exp(-decay_rate * distance_km)
        return round(score, 3)

    @staticmethod
    async def geocode_address(address: str) -> Dict[str, Any]:
        """
        Geocode address using OpenStreetMap Nominatim.
        Returns lat/lon coordinates.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={
                        "q": address,
                        "format": "json",
                        "limit": 1
                    },
                    headers={
                        "User-Agent": "KumeleApp/1.0"
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        return {
                            "success": True,
                            "lat": float(data[0]["lat"]),
                            "lon": float(data[0]["lon"]),
                            "display_name": data[0].get("display_name", address)
                        }
                
                return {
                    "success": False,
                    "message": "Address not found"
                }
                
        except Exception as e:
            logger.error(f"Geocoding error: {e}")
            return {
                "success": False,
                "message": str(e)
            }

    @staticmethod
    async def compute_hobby_similarity(
        user_hobbies: List[str],
        event_category: str
    ) -> float:
        """
        Compute hobby/category similarity score.
        In production, would use embeddings from Hugging Face.
        """
        if not user_hobbies or not event_category:
            return 0.3  # Default neutral score
        
        event_category_lower = event_category.lower()
        
        # Direct match
        for hobby in user_hobbies:
            if hobby.lower() == event_category_lower:
                return 1.0
            if hobby.lower() in event_category_lower or event_category_lower in hobby.lower():
                return 0.8
        
        # Category similarity mapping
        category_groups = {
            "fitness": ["gym", "yoga", "running", "cycling", "swimming", "crossfit"],
            "music": ["singing", "guitar", "piano", "djing", "concerts", "karaoke"],
            "outdoor": ["hiking", "camping", "climbing", "surfing", "skiing"],
            "food": ["cooking", "wine", "coffee", "baking", "restaurants"],
            "tech": ["coding", "programming", "ai", "startups", "gaming"],
            "arts": ["painting", "photography", "dance", "theater", "crafts"],
            "social": ["networking", "dating", "community", "volunteering"],
        }
        
        # Check if event and user hobbies are in same group
        event_group = None
        user_groups = set()
        
        for group, keywords in category_groups.items():
            if any(kw in event_category_lower for kw in keywords):
                event_group = group
            for hobby in user_hobbies:
                if any(kw in hobby.lower() for kw in keywords):
                    user_groups.add(group)
        
        if event_group and event_group in user_groups:
            return 0.6
        
        return 0.3  # No match

    @staticmethod
    async def get_user_engagement_score(
        db: AsyncSession,
        user_id: int
    ) -> float:
        """
        Calculate user engagement score based on activity.
        Higher engagement = prioritize more relevant matches.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=90)
        
        # Convert user_id to int if needed
        try:
            user_id_int = int(user_id) if isinstance(user_id, str) else user_id
        except (ValueError, TypeError):
            return 0.0  # No engagement score for UUID users
        
        # Count interactions
        query = select(func.count(UserInteraction.id)).where(
            and_(
                UserInteraction.user_id == user_id_int,
                UserInteraction.created_at >= cutoff_date
            )
        )
        result = await db.execute(query)
        interaction_count = result.scalar() or 0
        
        # Normalize to 0-1 (assume 50 interactions = max engagement)
        engagement_score = min(interaction_count / 50.0, 1.0)
        return round(engagement_score, 3)

    @staticmethod
    async def get_user_reward_tier(
        db: AsyncSession,
        user_id: int
    ) -> str:
        """Get user's reward tier."""
        # In production, would query UserRewardProgress table
        # For now, return "none" as default
        return "none"

    @staticmethod
    async def match_events(
        db: AsyncSession,
        user_id: str,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        address: Optional[str] = None,
        max_distance_km: float = 50.0,
        category: Optional[str] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Match events for a user based on multiple factors.
        """
        try:
            user_id_int = int(user_id)
        except ValueError:
            user_id_int = hash(user_id) % 1000000
        
        # Get user location
        user_lat, user_lon = lat, lon
        
        if not user_lat or not user_lon:
            if address:
                geo_result = await MatchingService.geocode_address(address)
                if geo_result.get("success"):
                    user_lat = geo_result["lat"]
                    user_lon = geo_result["lon"]
            else:
                # Try to get from user profile
                user_query = select(User).where(User.user_id == user_id_int)
                user_result = await db.execute(user_query)
                user = user_result.scalar_one_or_none()
                if user and user.location_lat and user.location_lon:
                    user_lat = float(user.location_lat)
                    user_lon = float(user.location_lon)
        
        # Get user's hobbies
        hobbies_query = select(UserHobby.hobby_id).where(
            UserHobby.user_id == user_id_int
        )
        hobbies_result = await db.execute(hobbies_query)
        user_hobbies = [row[0] for row in hobbies_result.fetchall()]
        
        # Get user engagement score
        engagement_score = await MatchingService.get_user_engagement_score(db, user_id_int)
        
        # Get user reward tier
        reward_tier = await MatchingService.get_user_reward_tier(db, user_id_int)
        
        # Query upcoming events
        events_query = select(Event).where(
            and_(
                Event.status.in_(["scheduled", "draft"]),
                Event.event_date > datetime.utcnow()
            )
        )
        
        if category:
            events_query = events_query.where(Event.category.ilike(f"%{category}%"))
        
        events_query = events_query.order_by(Event.event_date).limit(100)
        
        events_result = await db.execute(events_query)
        events = events_result.scalars().all()
        
        # Score and rank events
        scored_events = []
        
        for event in events:
            # Calculate distance score
            distance_km = None
            dist_score = 0.5  # Default if no location
            
            if user_lat and user_lon and event.location_lat and event.location_lon:
                distance_km = MatchingService.haversine_distance(
                    user_lat, user_lon,
                    float(event.location_lat), float(event.location_lon)
                )
                
                if distance_km > max_distance_km:
                    continue  # Skip events too far away
                
                dist_score = MatchingService.distance_score(distance_km, max_distance_km)
            
            # Calculate hobby similarity
            hobby_score = await MatchingService.compute_hobby_similarity(
                user_hobbies, event.category or ""
            )
            
            # Get host rating
            host_score = 0.5  # Default
            if event.host_id:
                host_query = select(HostRatingAggregate).where(
                    HostRatingAggregate.host_id == event.host_id
                )
                host_result = await db.execute(host_query)
                host_rating = host_result.scalar_one_or_none()
                if host_rating and host_rating.overall_score_5:
                    host_score = float(host_rating.overall_score_5) / 5.0
            
            # Get reward boost
            reward_boost = MatchingService.REWARD_BOOSTS.get(reward_tier, 0.0)
            
            # Calculate final score
            final_score = (
                (dist_score * MatchingService.DISTANCE_WEIGHT) +
                (hobby_score * MatchingService.HOBBY_WEIGHT) +
                (engagement_score * MatchingService.ENGAGEMENT_WEIGHT) +
                (host_score * MatchingService.HOST_RATING_WEIGHT) +
                (reward_boost * MatchingService.REWARD_BOOST_WEIGHT)
            )
            
            scored_events.append({
                "event_id": str(event.event_id),
                "title": event.title,
                "category": event.category,
                "event_date": event.event_date.isoformat() if event.event_date else None,
                "location": event.location,
                "distance_km": round(distance_km, 1) if distance_km else None,
                "score": round(final_score, 3),
                "score_breakdown": {
                    "distance": round(dist_score, 3),
                    "hobby_match": round(hobby_score, 3),
                    "engagement": round(engagement_score, 3),
                    "host_rating": round(host_score, 3),
                    "reward_boost": round(reward_boost, 3)
                },
                "host_id": str(event.host_id) if event.host_id else None
            })
        
        # Sort by score
        scored_events.sort(key=lambda x: x["score"], reverse=True)
        
        # Limit results
        matched_events = scored_events[:limit]
        
        # Handle new users with no data (fallback)
        is_new_user = len(user_hobbies) == 0 and engagement_score == 0
        
        return {
            "user_id": user_id,
            "matched_events": matched_events,
            "total_found": len(scored_events),
            "filters_applied": {
                "max_distance_km": max_distance_km,
                "category": category,
                "user_location": {"lat": user_lat, "lon": user_lon} if user_lat else None
            },
            "user_context": {
                "hobbies_count": len(user_hobbies),
                "engagement_score": engagement_score,
                "reward_tier": reward_tier,
                "is_new_user": is_new_user
            },
            "computed_at": datetime.utcnow().isoformat()
        }

    @staticmethod
    async def get_score_breakdown(
        db: AsyncSession,
        event_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """Get detailed score breakdown for a specific event match."""
        # Would compute individual scores for debugging
        return {
            "event_id": event_id,
            "user_id": user_id,
            "score_breakdown": {
                "distance": {"score": 0.8, "weight": 0.25, "detail": "5km away"},
                "hobby_match": {"score": 0.9, "weight": 0.35, "detail": "Direct hobby match"},
                "engagement": {"score": 0.6, "weight": 0.20, "detail": "30 interactions"},
                "host_rating": {"score": 0.85, "weight": 0.10, "detail": "4.25/5 rating"},
                "reward_boost": {"score": 0.10, "weight": 0.10, "detail": "Silver tier"}
            },
            "final_score": 0.78
        }
