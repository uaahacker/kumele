"""
Recommendation Service - Handles personalized recommendations using TFRS
"""
import logging
from typing import Dict, Any, List, Optional
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from kumele_ai.db.models import (
    User, Event, Hobby, UserHobby, UserEvent, BlogInteraction, AdInteraction
)
from kumele_ai.services.embed_service import embed_service
from kumele_ai.services.matching_service import matching_service

logger = logging.getLogger(__name__)


class RecommendationService:
    """Service for personalized recommendations using TFRS-style hybrid approach"""
    
    def __init__(self):
        self._model_loaded = False
        # In production, this would load a trained TFRS model
        # For now, we implement the logic using embeddings and collaborative filtering
    
    def _get_user_event_history(
        self,
        db: Session,
        user_id: int
    ) -> Dict[str, Any]:
        """Get user's event interaction history"""
        # Events attended
        attended = db.query(UserEvent).filter(
            and_(
                UserEvent.user_id == user_id,
                UserEvent.checked_in == True
            )
        ).all()
        
        # Events registered but not attended
        registered = db.query(UserEvent).filter(
            and_(
                UserEvent.user_id == user_id,
                UserEvent.checked_in == False
            )
        ).all()
        
        return {
            "attended_event_ids": [ue.event_id for ue in attended],
            "registered_event_ids": [ue.event_id for ue in registered]
        }
    
    def _get_collaborative_signals(
        self,
        db: Session,
        user_id: int
    ) -> List[int]:
        """Get event recommendations based on similar users' behavior"""
        # Find similar users
        similar_users = matching_service.find_similar_users(db, user_id, limit=20)
        similar_user_ids = [u["user_id"] for u in similar_users]
        
        if not similar_user_ids:
            return []
        
        # Get events attended by similar users
        user_history = self._get_user_event_history(db, user_id)
        excluded_events = set(
            user_history["attended_event_ids"] + 
            user_history["registered_event_ids"]
        )
        
        # Find popular events among similar users
        popular_events = db.query(
            UserEvent.event_id,
            func.count(UserEvent.id).label("count")
        ).filter(
            and_(
                UserEvent.user_id.in_(similar_user_ids),
                UserEvent.checked_in == True,
                ~UserEvent.event_id.in_(excluded_events) if excluded_events else True
            )
        ).group_by(UserEvent.event_id).order_by(
            func.count(UserEvent.id).desc()
        ).limit(50).all()
        
        return [e[0] for e in popular_events]
    
    def recommend_events(
        self,
        db: Session,
        user_id: int,
        limit: int = 20,
        include_exploration: bool = True
    ) -> List[Dict[str, Any]]:
        """Get personalized event recommendations (predicted preference)"""
        # Get content-based matches
        content_matches = matching_service.match_events(db, user_id, limit=limit * 2)
        
        # Get collaborative filtering signals
        collab_event_ids = self._get_collaborative_signals(db, user_id)
        
        # Combine scores
        recommendations = []
        seen_event_ids = set()
        
        # Process content matches
        for match in content_matches:
            event_id = match["event_id"]
            if event_id in seen_event_ids:
                continue
            
            # Boost score if also recommended by collaborative filtering
            collab_boost = 0.2 if event_id in collab_event_ids else 0.0
            
            preference_score = match["match_score"] * 0.7 + collab_boost * 0.3
            
            recommendations.append({
                **match,
                "preference_score": round(preference_score, 4),
                "recommendation_type": "hybrid"
            })
            seen_event_ids.add(event_id)
        
        # Add pure collaborative recommendations not in content matches
        for event_id in collab_event_ids[:limit // 2]:
            if event_id in seen_event_ids:
                continue
            
            event = db.query(Event).filter(Event.id == event_id).first()
            if event and event.status == "upcoming":
                recommendations.append({
                    "event_id": event.id,
                    "title": event.title,
                    "description": event.description,
                    "event_date": event.event_date.isoformat() if event.event_date else None,
                    "location": event.location,
                    "city": event.city,
                    "is_paid": event.is_paid,
                    "price": float(event.price) if event.price else 0,
                    "match_score": 0.5,
                    "preference_score": 0.6,
                    "recommendation_type": "collaborative"
                })
                seen_event_ids.add(event_id)
        
        # Add exploration items (occasionally surface low-status high-relevance)
        if include_exploration:
            explore_events = db.query(Event).filter(
                and_(
                    Event.status == "upcoming",
                    ~Event.id.in_(seen_event_ids) if seen_event_ids else True
                )
            ).order_by(func.random()).limit(3).all()
            
            for event in explore_events:
                recommendations.append({
                    "event_id": event.id,
                    "title": event.title,
                    "description": event.description,
                    "event_date": event.event_date.isoformat() if event.event_date else None,
                    "location": event.location,
                    "city": event.city,
                    "is_paid": event.is_paid,
                    "price": float(event.price) if event.price else 0,
                    "match_score": 0.3,
                    "preference_score": 0.35,
                    "recommendation_type": "exploration"
                })
        
        # Sort by preference score
        recommendations.sort(key=lambda x: x["preference_score"], reverse=True)
        
        return recommendations[:limit]
    
    def recommend_hobbies(
        self,
        db: Session,
        user_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Suggest new hobbies based on user behavior"""
        # Get user's current hobbies
        current_hobbies = db.query(UserHobby.hobby_id).filter(
            UserHobby.user_id == user_id
        ).all()
        current_hobby_ids = set(h[0] for h in current_hobbies)
        
        # Get hobbies from events attended
        attended_hobbies = db.query(Event.hobby_id).join(UserEvent).filter(
            and_(
                UserEvent.user_id == user_id,
                UserEvent.checked_in == True,
                Event.hobby_id.isnot(None),
                ~Event.hobby_id.in_(current_hobby_ids) if current_hobby_ids else True
            )
        ).distinct().all()
        attended_hobby_ids = [h[0] for h in attended_hobbies]
        
        # Get hobbies from similar users
        similar_users = matching_service.find_similar_users(db, user_id, limit=20)
        similar_user_ids = [u["user_id"] for u in similar_users]
        
        similar_user_hobbies = []
        if similar_user_ids:
            similar_user_hobbies = db.query(
                UserHobby.hobby_id,
                func.count(UserHobby.id).label("count")
            ).filter(
                and_(
                    UserHobby.user_id.in_(similar_user_ids),
                    ~UserHobby.hobby_id.in_(current_hobby_ids) if current_hobby_ids else True
                )
            ).group_by(UserHobby.hobby_id).order_by(
                func.count(UserHobby.id).desc()
            ).limit(20).all()
        
        # Score hobbies
        hobby_scores = {}
        
        # Events attended signal
        for hobby_id in attended_hobby_ids:
            hobby_scores[hobby_id] = hobby_scores.get(hobby_id, 0) + 0.4
        
        # Similar users signal
        for hobby_id, count in similar_user_hobbies:
            hobby_scores[hobby_id] = hobby_scores.get(hobby_id, 0) + min(count * 0.1, 0.3)
        
        # Get hobby details and format response
        recommendations = []
        for hobby_id, score in sorted(hobby_scores.items(), key=lambda x: x[1], reverse=True)[:limit]:
            hobby = db.query(Hobby).filter(Hobby.id == hobby_id).first()
            if hobby:
                recommendations.append({
                    "hobby_id": hobby.id,
                    "name": hobby.name,
                    "category": hobby.category,
                    "description": hobby.description,
                    "recommendation_score": round(score, 4),
                    "reason": self._get_recommendation_reason(
                        hobby_id in attended_hobby_ids,
                        hobby_id in [h[0] for h in similar_user_hobbies]
                    )
                })
        
        return recommendations
    
    def _get_recommendation_reason(
        self,
        from_events: bool,
        from_similar_users: bool
    ) -> str:
        """Get human-readable reason for recommendation"""
        if from_events and from_similar_users:
            return "Based on events you attended and users like you"
        elif from_events:
            return "Based on events you attended"
        elif from_similar_users:
            return "Popular among users with similar interests"
        return "You might be interested"


# Singleton instance
recommendation_service = RecommendationService()
