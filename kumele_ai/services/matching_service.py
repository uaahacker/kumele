"""
Matching Service - Handles event and user matching logic

Enhanced with:
- NFT Badge Influence: Users with badges get priority matching
- Verified Attendance Rate: Historical attendance influences trust
- Payment Urgency: 10-minute payment window affects ranking
- Host Reputation: Host tier and ratings affect event priority
"""
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from kumele_ai.db.models import (
    User, Event, Hobby, UserHobby, UserEvent, BlogInteraction,
    UserMLFeatures, NFTBadge, CheckIn, HostRating, EventMLFeatures
)
from kumele_ai.services.embed_service import embed_service
from kumele_ai.services.geocode_service import geocode_service

logger = logging.getLogger(__name__)


# ============================================================
# MATCHING WEIGHTS CONFIGURATION
# ============================================================

MATCHING_WEIGHTS = {
    # Base matching factors
    "distance": 0.25,           # Location proximity
    "hobby_similarity": 0.35,   # Interest alignment
    "engagement": 0.10,         # Past engagement
    
    # Trust & reputation factors (NEW)
    "verified_attendance": 0.10,  # User's attendance history
    "nft_badge": 0.08,           # NFT badge bonus
    "payment_urgency": 0.05,     # Payment behavior
    "host_reputation": 0.07,     # Host trust score
}

# NFT Badge trust multipliers
NFT_BADGE_MULTIPLIERS = {
    "Bronze": 1.02,
    "Silver": 1.05,
    "Gold": 1.10,
    "Platinum": 1.15,
    "Legendary": 1.25,
}

# Attendance rate thresholds for trust scoring
ATTENDANCE_TRUST_THRESHOLDS = {
    "high": 0.9,      # 90%+ attendance = full trust boost
    "medium": 0.7,    # 70-90% = partial trust boost
    "low": 0.5,       # 50-70% = no adjustment
    "risky": 0.3,     # 30-50% = slight penalty
}


class MatchingService:
    """
    Service for matching users to events based on objective relevance.
    
    Scoring factors:
    1. Distance Score: Haversine distance from user to event
    2. Hobby Similarity: Embedding cosine similarity
    3. Engagement Weight: Past interaction history
    4. Verified Attendance Score: Trust based on check-in history
    5. NFT Badge Bonus: Priority for badge holders
    6. Payment Urgency Score: Behavior around payment windows
    7. Host Reputation Score: Host tier and reliability
    """
    
    def __init__(self):
        self.max_distance_km = 100  # Maximum distance for matching
        self.payment_window_minutes = 10  # Payment urgency window
    
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
    
    # ============================================================
    # NEW: VERIFIED ATTENDANCE SCORING
    # ============================================================
    
    def calculate_verified_attendance_score(
        self,
        db: Session,
        user_id: int
    ) -> float:
        """
        Calculate trust score based on verified attendance history.
        
        Uses 90-day window:
        - 90%+ attendance = 1.0 (full trust)
        - 70-90% attendance = 0.8
        - 50-70% attendance = 0.5
        - <50% attendance = 0.2 (risky)
        """
        # Get pre-computed ML features
        user_ml = db.query(UserMLFeatures).filter(
            UserMLFeatures.user_id == user_id
        ).first()
        
        if user_ml and user_ml.attendance_rate_90d is not None:
            rate = user_ml.attendance_rate_90d
        else:
            # Calculate on the fly
            total_rsvps = db.query(UserEvent).filter(
                and_(
                    UserEvent.user_id == user_id,
                    UserEvent.created_at >= datetime.utcnow() - timedelta(days=90)
                )
            ).count()
            
            verified_checkins = db.query(CheckIn).filter(
                and_(
                    CheckIn.user_id == user_id,
                    CheckIn.is_valid == True,
                    CheckIn.check_in_time >= datetime.utcnow() - timedelta(days=90)
                )
            ).count()
            
            rate = verified_checkins / max(total_rsvps, 1)
        
        # Convert rate to trust score
        if rate >= ATTENDANCE_TRUST_THRESHOLDS["high"]:
            return 1.0
        elif rate >= ATTENDANCE_TRUST_THRESHOLDS["medium"]:
            return 0.8
        elif rate >= ATTENDANCE_TRUST_THRESHOLDS["low"]:
            return 0.5
        elif rate >= ATTENDANCE_TRUST_THRESHOLDS["risky"]:
            return 0.3
        else:
            return 0.2
    
    # ============================================================
    # NEW: NFT BADGE SCORING
    # ============================================================
    
    def calculate_nft_badge_score(
        self,
        db: Session,
        user_id: int
    ) -> Tuple[float, Optional[str]]:
        """
        Calculate NFT badge influence on matching.
        
        Returns:
            (score, badge_type): Score 0-1 and badge type if any
        """
        # Get user's active NFT badge
        badge = db.query(NFTBadge).filter(
            and_(
                NFTBadge.user_id == user_id,
                NFTBadge.is_active == True
            )
        ).order_by(NFTBadge.level.desc()).first()
        
        if not badge:
            return 0.0, None
        
        # Score based on badge level
        base_score = min(badge.level / 10, 1.0)  # Level 1-10 normalized
        
        # Apply badge type multiplier
        multiplier = NFT_BADGE_MULTIPLIERS.get(badge.badge_type, 1.0)
        
        return min(base_score * multiplier, 1.0), badge.badge_type
    
    # ============================================================
    # NEW: PAYMENT URGENCY SCORING
    # ============================================================
    
    def calculate_payment_urgency_score(
        self,
        db: Session,
        user_id: int
    ) -> float:
        """
        Calculate payment urgency score based on payment behavior.
        
        10-minute rule: Users who pay within 10 minutes get priority.
        """
        user_ml = db.query(UserMLFeatures).filter(
            UserMLFeatures.user_id == user_id
        ).first()
        
        if not user_ml or user_ml.avg_payment_time_minutes is None:
            return 0.5  # Neutral for new users
        
        avg_time = user_ml.avg_payment_time_minutes
        timeout_rate = user_ml.payment_timeout_rate or 0
        
        # Score based on payment speed
        if avg_time <= self.payment_window_minutes:
            speed_score = 1.0
        elif avg_time <= 30:
            speed_score = 0.7
        elif avg_time <= 60:
            speed_score = 0.4
        else:
            speed_score = 0.2
        
        # Penalize high timeout rate
        timeout_penalty = timeout_rate * 0.5
        
        return max(speed_score - timeout_penalty, 0.0)
    
    # ============================================================
    # NEW: HOST REPUTATION SCORING
    # ============================================================
    
    def calculate_host_reputation_score(
        self,
        db: Session,
        event: Event
    ) -> float:
        """
        Calculate host reputation score.
        
        Factors:
        - Host tier (Bronze/Silver/Gold)
        - Average host rating
        - Total events hosted
        - Host reliability (no-show rate)
        """
        if not event.host_id:
            return 0.5
        
        # Get host ML features
        host_ml = db.query(UserMLFeatures).filter(
            UserMLFeatures.user_id == event.host_id
        ).first()
        
        # Get host ratings
        host_ratings = db.query(
            func.avg(HostRating.overall_rating),
            func.count(HostRating.id)
        ).filter(
            HostRating.host_id == event.host_id
        ).first()
        
        avg_rating = host_ratings[0] or 3.0
        total_ratings = host_ratings[1] or 0
        
        # Base score from rating (1-5 scale normalized)
        rating_score = (avg_rating - 1) / 4
        
        # Tier bonus
        tier_bonus = 0.0
        if host_ml:
            tier_bonuses = {"Bronze": 0.05, "Silver": 0.10, "Gold": 0.15}
            tier_bonus = tier_bonuses.get(host_ml.reward_tier, 0.0)
        
        # Experience bonus (more events = more trustworthy)
        experience_bonus = min(total_ratings / 100, 0.1)
        
        return min(rating_score + tier_bonus + experience_bonus, 1.0)
    
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
        
        Enhanced scoring factors:
        - Distance: Haversine distance from user to event (25%)
        - Hobby Similarity: Embedding cosine similarity (35%)
        - Engagement: Past interaction history (10%)
        - Verified Attendance: User's attendance track record (10%)
        - NFT Badge: Badge holder priority (8%)
        - Payment Urgency: Payment behavior (5%)
        - Host Reputation: Host tier and reliability (7%)
        
        If location_filter is provided as a string, it will be geocoded using
        Nominatim to get lat/lon coordinates for distance calculations.
        """
        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return []
        
        # Get user's hobby embeddings
        user_hobby_embeddings = self.get_user_hobby_embeddings(db, user_id)
        
        # Calculate user-level scores (computed once per request)
        verified_attendance_score = self.calculate_verified_attendance_score(db, user_id)
        nft_badge_score, nft_badge_type = self.calculate_nft_badge_score(db, user_id)
        payment_urgency_score = self.calculate_payment_urgency_score(db, user_id)
        
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
                engagement_score = (engagement_weight - 1.0) / 0.5  # Normalize to 0-1
                
                # Calculate host reputation score
                host_reputation_score = self.calculate_host_reputation_score(db, event)
                
                # Combined match score (weighted sum)
                match_score = (
                    distance_score * MATCHING_WEIGHTS["distance"] +
                    hobby_similarity * MATCHING_WEIGHTS["hobby_similarity"] +
                    engagement_score * MATCHING_WEIGHTS["engagement"] +
                    verified_attendance_score * MATCHING_WEIGHTS["verified_attendance"] +
                    nft_badge_score * MATCHING_WEIGHTS["nft_badge"] +
                    payment_urgency_score * MATCHING_WEIGHTS["payment_urgency"] +
                    host_reputation_score * MATCHING_WEIGHTS["host_reputation"]
                )
                
                # Apply NFT badge multiplier to final score
                if nft_badge_type:
                    match_score *= NFT_BADGE_MULTIPLIERS.get(nft_badge_type, 1.0)
                
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
                    # Detailed scoring breakdown
                    "score_breakdown": {
                        "distance_score": round(distance_score, 4),
                        "hobby_similarity": round(hobby_similarity, 4),
                        "engagement_score": round(engagement_score, 4),
                        "verified_attendance_score": round(verified_attendance_score, 4),
                        "nft_badge_score": round(nft_badge_score, 4),
                        "payment_urgency_score": round(payment_urgency_score, 4),
                        "host_reputation_score": round(host_reputation_score, 4),
                    },
                    # User trust signals
                    "user_trust": {
                        "nft_badge_type": nft_badge_type,
                        "verified_attendance_rate": round(verified_attendance_score, 4),
                    }
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
