"""
Recommendation Service for Personalized Recommendations.
Uses collaborative filtering and content-based approaches.
"""
from typing import Optional, List, Dict, Any, Tuple, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, text
from datetime import datetime, timedelta
import logging
import numpy as np
from collections import defaultdict

from app.models.database_models import (
    User, Event, UserInteraction, UserHobby, 
    InterestTaxonomy, InterestTranslation, RecommendationCache,
    EventAttendance, HostRatingAggregate
)
from app.config import settings

logger = logging.getLogger(__name__)


class RecommendationService:
    """Service for generating personalized recommendations."""
    
    # Interaction weights for collaborative filtering
    INTERACTION_WEIGHTS = {
        "attend": 5.0,
        "rsvp": 3.0,
        "click": 1.0,
        "view": 0.5,
        "like": 2.0,
    }
    
    # Number of recommendations to return
    TOP_K = 10
    
    # Default hobbies for new/unknown users
    DEFAULT_HOBBIES = [
        {"hobby_id": "photography", "hobby_name": "Photography", "score": 0.85, "reason": "Popular hobby"},
        {"hobby_id": "hiking", "hobby_name": "Hiking", "score": 0.82, "reason": "Popular hobby"},
        {"hobby_id": "cooking", "hobby_name": "Cooking", "score": 0.80, "reason": "Popular hobby"},
        {"hobby_id": "gaming", "hobby_name": "Gaming", "score": 0.78, "reason": "Popular hobby"},
        {"hobby_id": "music", "hobby_name": "Music", "score": 0.75, "reason": "Popular hobby"},
        {"hobby_id": "yoga", "hobby_name": "Yoga", "score": 0.72, "reason": "Popular hobby"},
        {"hobby_id": "painting", "hobby_name": "Painting", "score": 0.70, "reason": "Popular hobby"},
        {"hobby_id": "reading", "hobby_name": "Reading", "score": 0.68, "reason": "Popular hobby"},
        {"hobby_id": "cycling", "hobby_name": "Cycling", "score": 0.65, "reason": "Popular hobby"},
        {"hobby_id": "dancing", "hobby_name": "Dancing", "score": 0.62, "reason": "Popular hobby"},
    ]

    @staticmethod
    async def get_user_interactions(
        db: AsyncSession,
        user_id: Union[int, str]
    ) -> List[Dict[str, Any]]:
        """Get user's interaction history."""
        try:
            query = select(UserInteraction).where(
                UserInteraction.user_id == user_id
            ).order_by(desc(UserInteraction.created_at)).limit(1000)
            
            result = await db.execute(query)
            interactions = result.scalars().all()
        
            return [
                {
                    "item_type": i.item_type,
                    "item_id": i.item_id,
                    "interaction_type": i.interaction_type,
                    "score": float(i.score or 1.0),
                    "created_at": i.created_at
                }
                for i in interactions
            ]
        except Exception as e:
            logger.warning(f"Could not get user interactions for {user_id}: {e}")
            return []

    @staticmethod
    async def get_user_hobbies(
        db: AsyncSession,
        user_id: Union[int, str]
    ) -> List[Dict[str, Any]]:
        """Get user's hobby preferences."""
        try:
            query = select(UserHobby, InterestTaxonomy).join(
                InterestTaxonomy,
                UserHobby.hobby_id == InterestTaxonomy.interest_id
            ).where(
                and_(
                    UserHobby.user_id == user_id,
                    InterestTaxonomy.is_active == True
                )
            )
            
            result = await db.execute(query)
            rows = result.fetchall()
            
            return [
                {
                    "hobby_id": row.UserHobby.hobby_id,
                    "preference_score": float(row.UserHobby.preference_score or 1.0)
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"Could not get user hobbies for {user_id}: {e}")
            return []

    @staticmethod
    async def get_similar_users(
        db: AsyncSession,
        user_id: Union[int, str],
        limit: int = 50
    ) -> List[Union[int, str]]:
        """Find users with similar interaction patterns."""
        try:
            # Get current user's interactions
            user_interactions = await RecommendationService.get_user_interactions(db, user_id)
            
            if not user_interactions:
                return []
            
            # Get items the user has interacted with
            user_items = set(
                (i["item_type"], i["item_id"]) 
                for i in user_interactions
            )
            
            # Find other users who interacted with same items
            item_ids = [i["item_id"] for i in user_interactions if i["item_type"] == "event"]
            
            if not item_ids:
                return []
            
            similar_query = select(
                UserInteraction.user_id,
                func.count(UserInteraction.item_id).label("overlap_count")
            ).where(
                and_(
                    UserInteraction.item_type == "event",
                    UserInteraction.item_id.in_(item_ids),
                    UserInteraction.user_id != user_id
                )
            ).group_by(
                UserInteraction.user_id
            ).order_by(
                desc("overlap_count")
            ).limit(limit)
            
            result = await db.execute(similar_query)
            similar_users = [row.user_id for row in result.fetchall()]
            
            return similar_users
        except Exception as e:
            logger.warning(f"Could not get similar users for {user_id}: {e}")
            return []

    @staticmethod
    async def recommend_hobbies(
        db: AsyncSession,
        user_id: Union[int, str],
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Recommend new hobbies based on:
        - Events attended
        - Content engagement
        - Similar users' preferences
        
        Returns default recommendations for new/unknown users.
        """
        try:
            # Get user's current hobbies
            user_hobbies = await RecommendationService.get_user_hobbies(db, user_id)
            current_hobby_ids = set(h["hobby_id"] for h in user_hobbies)
            
            # Get hobbies from attended events
            attended_query = select(Event.category).join(
                EventAttendance,
                Event.event_id == EventAttendance.event_id
            ).where(
                and_(
                    EventAttendance.user_id == user_id,
                    EventAttendance.checked_in == True
                )
            ).distinct()
            
            attended_result = await db.execute(attended_query)
            attended_categories = set(row[0] for row in attended_result.fetchall() if row[0])
            
            # Get similar users
            similar_users = await RecommendationService.get_similar_users(db, user_id)
            
            # Get hobbies of similar users
            hobby_scores = defaultdict(float)
            
            if similar_users:
                similar_hobbies_query = select(
                    UserHobby.hobby_id,
                    func.sum(UserHobby.preference_score).label("total_score")
                ).where(
                    UserHobby.user_id.in_(similar_users)
                ).group_by(
                    UserHobby.hobby_id
                )
                
                result = await db.execute(similar_hobbies_query)
                for row in result.fetchall():
                    if row.hobby_id not in current_hobby_ids:
                        hobby_scores[row.hobby_id] += float(row.total_score or 0) * 0.5
            
            # Boost hobbies related to attended event categories
            taxonomy_query = select(InterestTaxonomy).where(
                InterestTaxonomy.is_active == True
            )
            result = await db.execute(taxonomy_query)
            all_hobbies = result.scalars().all()
            
            for hobby in all_hobbies:
                if hobby.interest_id in current_hobby_ids:
                    continue
                
                # Check if hobby name matches attended categories
                hobby_name = hobby.interest_id.split(".")[-1].lower()
                for category in attended_categories:
                    if category and hobby_name in category.lower():
                        hobby_scores[hobby.interest_id] += 3.0
            
            # Get hobby labels
            hobby_ids = list(hobby_scores.keys())
            if not hobby_ids:
                # Return popular hobbies if no personalization available
                popular_query = select(
                    UserHobby.hobby_id,
                    func.count(UserHobby.user_id).label("user_count")
                ).group_by(
                    UserHobby.hobby_id
                ).order_by(
                    desc("user_count")
                ).limit(limit)
                
                result = await db.execute(popular_query)
                hobby_ids = [row.hobby_id for row in result.fetchall() if row.hobby_id not in current_hobby_ids]
                hobby_scores = {hid: 0.5 for hid in hobby_ids}
            
            # Get translations for hobbies
            translations_query = select(InterestTranslation).where(
                and_(
                    InterestTranslation.interest_id.in_(hobby_ids),
                    InterestTranslation.language_code == "en"
                )
            )
            result = await db.execute(translations_query)
            translations = {t.interest_id: t.label for t in result.scalars().all()}
            
            # Sort and return top recommendations
            sorted_hobbies = sorted(
                hobby_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )[:limit]
            
            # Normalize scores
            max_score = max(s for _, s in sorted_hobbies) if sorted_hobbies else 1.0
            
            recommendations = [
                {
                    "hobby_id": hobby_id,
                    "hobby_name": translations.get(hobby_id, hobby_id.replace(".", " ").title()),
                    "score": round(score / max_score, 2) if max_score > 0 else 0.5,
                    "reason": "Based on similar users" if score > 0.5 else "Popular hobby"
                }
                for hobby_id, score in sorted_hobbies
            ]
            
            # If no recommendations found, return defaults
            if not recommendations:
                return {
                    "user_id": str(user_id),
                    "recommendations": RecommendationService.DEFAULT_HOBBIES[:limit],
                    "cached": False
                }
            
            return {
                "user_id": str(user_id),
                "recommendations": recommendations,
                "cached": False
            }
            
        except Exception as e:
            logger.warning(f"Could not generate hobby recommendations for {user_id}: {e}")
            # Return default recommendations on error
            return {
                "user_id": str(user_id),
                "recommendations": RecommendationService.DEFAULT_HOBBIES[:limit],
                "cached": False
            }

    @staticmethod
    async def recommend_events(
        db: AsyncSession,
        user_id: Union[int, str],
        location: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Recommend upcoming events based on:
        - Hobby preferences
        - Past RSVPs
        - Engagement history
        - Host quality (Gold/Silver/Bronze)
        
        Returns default recommendations for new/unknown users.
        """
        try:
            # Get user data
            user_query = select(User).where(User.user_id == user_id)
            result = await db.execute(user_query)
            user = result.scalar_one_or_none()
            
            # Get user's hobbies
            user_hobbies = await RecommendationService.get_user_hobbies(db, user_id)
            hobby_ids = [h["hobby_id"] for h in user_hobbies]
            
            # Get user's past attended events
            attended_query = select(EventAttendance.event_id).where(
                and_(
                    EventAttendance.user_id == user_id,
                    EventAttendance.checked_in == True
                )
            )
            result = await db.execute(attended_query)
            attended_event_ids = set(row[0] for row in result.fetchall())
            
            # Get upcoming events
            now = datetime.utcnow()
            events_query = select(Event).where(
                and_(
                    Event.event_date > now,
                    Event.status.in_(["scheduled", "ongoing"]),
                    ~Event.event_id.in_(attended_event_ids) if attended_event_ids else True
                )
            ).limit(200)
            
            result = await db.execute(events_query)
            upcoming_events = result.scalars().all()
            
            if not upcoming_events:
                return {
                    "user_id": str(user_id),
                    "recommendations": [],
                    "cached": False
                }
            
            # Get host ratings for scoring
            host_ids = list(set(e.host_id for e in upcoming_events))
            ratings_query = select(HostRatingAggregate).where(
                HostRatingAggregate.host_id.in_(host_ids)
            )
            result = await db.execute(ratings_query)
            host_ratings = {r.host_id: r for r in result.scalars().all()}
            
            # Score events
            event_scores = []
            
            for event in upcoming_events:
                score = 0.0
                
                # Hobby match (highest weight)
                if event.category:
                    category_lower = event.category.lower()
                    for hobby in hobby_ids:
                        if hobby.split(".")[-1].lower() in category_lower:
                            score += 5.0
                            break
                
                # Host quality bonus
                host_rating = host_ratings.get(event.host_id)
                if host_rating:
                    # Score based on overall rating (0-5 scale)
                    score += float(host_rating.overall_score_5 or 0) * 0.5
                    
                    # Badge bonuses
                    if host_rating.badges:
                        if "Reliable Organiser" in host_rating.badges:
                            score += 1.0
                        if "Community Favorite" in host_rating.badges:
                            score += 0.5
                
                # Location proximity (if user has location)
                if user and user.location_lat and event.location_lat:
                    # Simple distance scoring (closer = better)
                    dist = abs(float(user.location_lat) - float(event.location_lat)) + \
                           abs(float(user.location_lon or 0) - float(event.location_lon or 0))
                    if dist < 1:  # Very close
                        score += 2.0
                    elif dist < 5:  # Nearby
                        score += 1.0
                
                # Time relevance (events sooner get slight boost)
                days_until = (event.event_date - now).days if event.event_date else 30
                if days_until <= 7:
                    score += 1.0
                elif days_until <= 14:
                    score += 0.5
                
                # Price consideration (free events get slight boost)
                if event.price == 0 or event.price is None:
                    score += 0.3
                
                event_scores.append({
                    "event": event,
                    "score": score
                })
            
            # Sort by score
            event_scores.sort(key=lambda x: x["score"], reverse=True)
            top_events = event_scores[:limit]
            
            # Normalize scores
            max_score = max(e["score"] for e in top_events) if top_events else 1.0
            
            recommendations = [
                {
                    "event_id": str(e["event"].event_id),
                    "title": e["event"].title,
                    "category": e["event"].category,
                    "event_date": str(e["event"].event_date) if e["event"].event_date else None,
                    "score": round(e["score"] / max_score, 2) if max_score > 0 else 0.5
                }
                for e in top_events
            ]
            
            return {
                "user_id": str(user_id),
                "recommendations": recommendations,
                "cached": False
            }
            
        except Exception as e:
            logger.warning(f"Could not generate event recommendations for {user_id}: {e}")
            return {
                "user_id": str(user_id),
                "recommendations": [],
                "cached": False
            }

    @staticmethod
    async def cache_recommendations(
        db: AsyncSession,
        user_id: Union[int, str],
        rec_type: str,
        recommendations: List[Dict[str, Any]],
        ttl_hours: int = 24
    ):
        """Cache recommendations for faster retrieval."""
        try:
            # Delete old cache
            from sqlalchemy import delete
            delete_query = delete(RecommendationCache).where(
                and_(
                    RecommendationCache.user_id == user_id,
                    RecommendationCache.recommendation_type == rec_type
                )
            )
            await db.execute(delete_query)
            
            # Create new cache entry
            cache = RecommendationCache(
                user_id=user_id,
                recommendation_type=rec_type,
                recommendations=recommendations,
                computed_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=ttl_hours)
            )
            db.add(cache)
            await db.flush()
        except Exception as e:
            logger.warning(f"Could not cache recommendations: {e}")

    @staticmethod
    async def get_cached_recommendations(
        db: AsyncSession,
        user_id: Union[int, str],
        recommendation_type: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Get cached recommendations if still valid."""
        try:
            query = select(RecommendationCache).where(
                and_(
                    RecommendationCache.user_id == user_id,
                    RecommendationCache.recommendation_type == recommendation_type,
                    RecommendationCache.expires_at > datetime.utcnow()
                )
            )
            
            result = await db.execute(query)
            cache = result.scalar_one_or_none()
            
            if cache:
                return cache.recommendations
        except Exception as e:
            logger.warning(f"Could not get cached recommendations: {e}")
        return None
