"""
Matching Service - Handles event and user matching logic
"""
import logging
import math
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from kumele_ai.db.models import (
    User, Event, Hobby, UserHobby, UserEvent, BlogInteraction
)
from kumele_ai.services.embed_service import embed_service
from kumele_ai.services.geocode_service import geocode_service

logger = logging.getLogger(__name__)


class MatchingService:
    """Service for matching users to events based on relevance"""
    
    def __init__(self):
        self.max_distance_km = 100  # Maximum distance for matching
    
    def haversine_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """Calculate haversine distance between two points in km"""
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
    
    def calculate_distance_score(self, distance_km: float) -> float:
        """Calculate distance score (0-1, higher is better)"""
        if distance_km <= 0:
            return 1.0
        if distance_km >= self.max_distance_km:
            return 0.0
        return 1.0 - (distance_km / self.max_distance_km)
    
    def calculate_hobby_similarity(
        self,
        user_hobby_embeddings: List[List[float]],
        event_embedding: List[float]
    ) -> float:
        """Calculate hobby similarity between user and event"""
        if not user_hobby_embeddings or not event_embedding:
            return 0.0
        
        # Find max similarity across user's hobbies
        max_similarity = 0.0
        for user_emb in user_hobby_embeddings:
            sim = embed_service.compute_similarity(user_emb, event_embedding)
            max_similarity = max(max_similarity, sim)
        
        return max_similarity
    
    def calculate_engagement_weight(
        self,
        db: Session,
        user_id: int,
        event: Event
    ) -> float:
        """Calculate engagement weight based on past interactions"""
        weight = 1.0
        
        # Check if user has attended similar events
        similar_events = db.query(UserEvent).join(Event).filter(
            and_(
                UserEvent.user_id == user_id,
                UserEvent.checked_in == True,
                Event.hobby_id == event.hobby_id
            )
        ).count()
        
        if similar_events > 0:
            weight += min(similar_events * 0.1, 0.3)  # Max 30% boost
        
        # Check if user has interacted with related blogs
        blog_interactions = db.query(BlogInteraction).filter(
            BlogInteraction.user_id == user_id
        ).count()
        
        if blog_interactions > 0:
            weight += min(blog_interactions * 0.02, 0.1)  # Max 10% boost
        
        return min(weight, 1.5)  # Cap at 1.5x
    
    def get_user_hobby_embeddings(
        self,
        db: Session,
        user_id: int
    ) -> List[List[float]]:
        """Get embeddings for user's hobbies"""
        user_hobbies = db.query(UserHobby).join(Hobby).filter(
            UserHobby.user_id == user_id
        ).all()
        
        embeddings = []
        for uh in user_hobbies:
            try:
                emb = embed_service.embed_hobby(
                    uh.hobby.name,
                    uh.hobby.description
                )
                embeddings.append(emb)
            except Exception as e:
                logger.error(f"Error embedding hobby: {e}")
        
        return embeddings
    
    def get_event_embedding(self, event: Event) -> List[float]:
        """Get embedding for an event"""
        tags = event.hobby_tags if event.hobby_tags else []
        return embed_service.embed_event(
            event.title,
            event.description,
            tags
        )
    
    def match_events(
        self,
        db: Session,
        user_id: int,
        limit: int = 20,
        hobby_filter: Optional[str] = None,
        location_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Match events to a user based on objective relevance.
        
        If location_filter is provided as a string, it will be geocoded using
        Nominatim to get lat/lon coordinates for distance calculations.
        """
        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return []
        
        # Get user's hobby embeddings
        user_hobby_embeddings = self.get_user_hobby_embeddings(db, user_id)
        
        # Determine search coordinates
        # Priority: location_filter (geocoded) > user's stored coordinates
        search_lat: Optional[float] = None
        search_lon: Optional[float] = None
        geocoded_location: Optional[str] = None
        
        if location_filter:
            # Geocode the location string using Nominatim
            geocode_result = geocode_service.geocode(location_filter)
            if geocode_result and geocode_result.get("found"):
                search_lat = geocode_result["latitude"]
                search_lon = geocode_result["longitude"]
                geocoded_location = geocode_result.get("display_name", location_filter)
                logger.info(f"Geocoded location '{location_filter}' -> ({search_lat}, {search_lon})")
            else:
                logger.warning(f"Could not geocode location: {location_filter}")
        
        # Fall back to user's stored coordinates if no geocoded location
        if search_lat is None and user.latitude and user.longitude:
            search_lat = user.latitude
            search_lon = user.longitude
        
        # Query upcoming events
        query = db.query(Event).filter(
            Event.status == "upcoming"
        )
        
        if hobby_filter:
            query = query.join(Hobby).filter(Hobby.name.ilike(f"%{hobby_filter}%"))
        
        # Note: We don't filter by city name when location is geocoded
        # Instead we compute distances and let the scoring handle it
        
        events = query.all()
        
        # Score each event
        scored_events = []
        for event in events:
            try:
                # Calculate distance score
                distance_score = 0.5  # Default if no location
                distance_km = None
                
                if search_lat is not None and search_lon is not None and event.latitude and event.longitude:
                    distance_km = self.haversine_distance(
                        search_lat, search_lon,
                        event.latitude, event.longitude
                    )
                    distance_score = self.calculate_distance_score(distance_km)
                
                # Calculate hobby similarity
                event_embedding = self.get_event_embedding(event)
                hobby_similarity = self.calculate_hobby_similarity(
                    user_hobby_embeddings,
                    event_embedding
                )
                
                # Calculate engagement weight
                engagement_weight = self.calculate_engagement_weight(db, user_id, event)
                
                # Combined match score (objective relevance)
                # Weights: distance 30%, hobby 50%, engagement 20%
                match_score = (
                    distance_score * 0.3 +
                    hobby_similarity * 0.5 +
                    (engagement_weight - 1.0) * 0.2  # Normalize engagement weight
                )
                
                event_data = {
                    "event_id": event.id,
                    "title": event.title,
                    "description": event.description,
                    "event_date": event.event_date.isoformat() if event.event_date else None,
                    "location": event.location,
                    "city": event.city,
                    "is_paid": event.is_paid,
                    "price": float(event.price) if event.price else 0,
                    "match_score": round(match_score, 4),
                    "distance_score": round(distance_score, 4),
                    "hobby_similarity": round(hobby_similarity, 4),
                    "engagement_weight": round(engagement_weight, 4)
                }
                
                # Include distance in km if calculated
                if distance_km is not None:
                    event_data["distance_km"] = round(distance_km, 2)
                
                # Include geocoded location info if used
                if geocoded_location:
                    event_data["search_location"] = geocoded_location
                
                scored_events.append(event_data)
                
            except Exception as e:
                logger.error(f"Error scoring event {event.id}: {e}")
        
        # Sort by match score descending
        scored_events.sort(key=lambda x: x["match_score"], reverse=True)
        
        return scored_events[:limit]
        
        # Sort by match score descending
        scored_events.sort(key=lambda x: x["match_score"], reverse=True)
        
        return scored_events[:limit]
    
    def find_similar_users(
        self,
        db: Session,
        user_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Find users with similar hobbies and engagement patterns"""
        # Get user's hobbies
        user_hobbies = db.query(UserHobby.hobby_id).filter(
            UserHobby.user_id == user_id
        ).all()
        hobby_ids = [h[0] for h in user_hobbies]
        
        if not hobby_ids:
            return []
        
        # Find users with overlapping hobbies
        similar_users = db.query(
            UserHobby.user_id,
            func.count(UserHobby.hobby_id).label("overlap_count")
        ).filter(
            and_(
                UserHobby.user_id != user_id,
                UserHobby.hobby_id.in_(hobby_ids)
            )
        ).group_by(UserHobby.user_id).order_by(
            func.count(UserHobby.hobby_id).desc()
        ).limit(limit).all()
        
        return [
            {"user_id": u[0], "hobby_overlap": u[1]}
            for u in similar_users
        ]


# Singleton instance
matching_service = MatchingService()
