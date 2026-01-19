"""
Ads Service - Handles ad intelligence and performance prediction
"""
import logging
from typing import Dict, Any, List, Optional
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from kumele_ai.db.models import (
    Ad, AdInteraction, User, UserHobby, Hobby
)
from kumele_ai.services.embed_service import embed_service
from kumele_ai.services.classify_service import classify_service

logger = logging.getLogger(__name__)


class AdsService:
    """Service for ad targeting and performance prediction"""
    
    def __init__(self):
        pass
    
    def _extract_themes_from_text(self, text: str) -> List[str]:
        """Extract hobby themes from ad text"""
        # Common hobby keywords
        hobby_keywords = {
            "sports": ["football", "basketball", "tennis", "soccer", "running", "gym", "fitness"],
            "arts": ["painting", "drawing", "music", "dance", "photography", "craft"],
            "outdoors": ["hiking", "camping", "cycling", "fishing", "gardening", "nature"],
            "gaming": ["gaming", "video games", "esports", "board games", "chess"],
            "cooking": ["cooking", "baking", "food", "culinary", "recipe"],
            "tech": ["coding", "programming", "technology", "robotics", "ai"],
            "reading": ["books", "reading", "literature", "writing", "poetry"],
            "social": ["networking", "meetup", "community", "social", "friends"]
        }
        
        text_lower = text.lower()
        found_themes = []
        
        for theme, keywords in hobby_keywords.items():
            if any(kw in text_lower for kw in keywords):
                found_themes.append(theme)
        
        return found_themes or ["general"]
    
    def match_audience(
        self,
        db: Session,
        title: str,
        description: str,
        image_tags: Optional[List[str]] = None,
        target_hobby: Optional[str] = None,
        target_location: Optional[str] = None
    ) -> Dict[str, Any]:
        """Match ad to relevant audience segments"""
        try:
            # Extract themes from text
            ad_text = f"{title} {description}"
            themes = self._extract_themes_from_text(ad_text)
            
            if image_tags:
                themes.extend(image_tags)
            
            if target_hobby:
                themes.append(target_hobby)
            
            themes = list(set(themes))
            
            # Generate embedding for ad
            ad_embedding = embed_service.embed_text(ad_text)
            
            # Find matching hobbies
            all_hobbies = db.query(Hobby).all()
            hobby_matches = []
            
            for hobby in all_hobbies:
                hobby_emb = embed_service.embed_hobby(hobby.name, hobby.description)
                similarity = embed_service.compute_similarity(ad_embedding, hobby_emb)
                
                if similarity > 0.3:  # Threshold
                    hobby_matches.append({
                        "hobby_id": hobby.id,
                        "hobby_name": hobby.name,
                        "similarity": round(similarity, 4)
                    })
            
            hobby_matches.sort(key=lambda x: x["similarity"], reverse=True)
            top_hobbies = hobby_matches[:5]
            
            # Build audience segments
            segments = []
            
            # Segment by hobby
            if top_hobbies:
                hobby_ids = [h["hobby_id"] for h in top_hobbies]
                hobby_users = db.query(func.count(UserHobby.user_id.distinct())).filter(
                    UserHobby.hobby_id.in_(hobby_ids)
                ).scalar() or 0
                
                segments.append({
                    "segment_name": "Hobby Enthusiasts",
                    "user_count": hobby_users,
                    "match_type": "hobby_similarity",
                    "matched_hobbies": [h["hobby_name"] for h in top_hobbies],
                    "relevance_score": round(np.mean([h["similarity"] for h in top_hobbies]), 4)
                })
            
            # Segment by location
            if target_location:
                location_users = db.query(func.count(User.id)).filter(
                    User.city.ilike(f"%{target_location}%")
                ).scalar() or 0
                
                segments.append({
                    "segment_name": f"Users in {target_location}",
                    "user_count": location_users,
                    "match_type": "location",
                    "relevance_score": 0.8
                })
            
            # Active users segment
            from datetime import datetime, timedelta
            recent_cutoff = datetime.utcnow() - timedelta(days=30)
            active_users = db.query(func.count(User.id)).filter(
                User.is_active == True
            ).scalar() or 0
            
            segments.append({
                "segment_name": "Active Users",
                "user_count": active_users,
                "match_type": "engagement",
                "relevance_score": 0.5
            })
            
            # Sort by relevance
            segments.sort(key=lambda x: x["relevance_score"], reverse=True)
            
            return {
                "extracted_themes": themes,
                "matched_hobbies": top_hobbies,
                "audience_segments": segments,
                "total_potential_reach": sum(s["user_count"] for s in segments),
                "recommendation": segments[0]["segment_name"] if segments else None
            }
            
        except Exception as e:
            logger.error(f"Audience matching error: {e}")
            return {
                "extracted_themes": [],
                "matched_hobbies": [],
                "audience_segments": [],
                "error": str(e)
            }
    
    def predict_performance(
        self,
        db: Session,
        title: str,
        description: str,
        image_tags: Optional[List[str]] = None,
        target_hobby: Optional[str] = None,
        budget: float = 100.0
    ) -> Dict[str, Any]:
        """Predict ad CTR and engagement before going live"""
        try:
            ad_text = f"{title} {description}"
            
            # Analyze text quality
            text_length = len(ad_text)
            has_call_to_action = any(cta in ad_text.lower() for cta in [
                "join", "sign up", "register", "learn more", "discover", "try", "get started"
            ])
            
            # Sentiment analysis
            sentiment = classify_service.analyze_sentiment(ad_text)
            
            # Base CTR estimation (industry average ~2%)
            base_ctr = 0.02
            
            # Adjustments
            # Text quality
            if 50 < text_length < 200:
                base_ctr *= 1.1
            elif text_length > 300:
                base_ctr *= 0.9
            
            # Call to action
            if has_call_to_action:
                base_ctr *= 1.2
            
            # Sentiment
            if sentiment.get("sentiment") == "positive":
                base_ctr *= 1.1
            elif sentiment.get("sentiment") == "negative":
                base_ctr *= 0.8
            
            # Image tags impact
            if image_tags and len(image_tags) >= 3:
                base_ctr *= 1.15
            
            # Historical comparison
            historical_avg_ctr = db.query(
                func.avg(
                    func.count(AdInteraction.id).filter(AdInteraction.interaction_type == "click") /
                    func.count(AdInteraction.id).filter(AdInteraction.interaction_type == "impression")
                )
            ).scalar() or 0.02
            
            predicted_ctr = (base_ctr + historical_avg_ctr) / 2
            
            # Calculate expected metrics
            expected_impressions = budget / 0.01  # Assuming $0.01 CPM
            expected_clicks = expected_impressions * predicted_ctr
            expected_conversions = expected_clicks * 0.1  # 10% conversion rate
            
            # Optimization tips
            tips = []
            if not has_call_to_action:
                tips.append("Add a clear call-to-action (e.g., 'Join Now', 'Learn More')")
            if text_length > 200:
                tips.append("Consider shortening the description for better engagement")
            if text_length < 50:
                tips.append("Add more descriptive content to improve relevance")
            if not image_tags:
                tips.append("Add relevant image tags to improve targeting")
            if sentiment.get("sentiment") == "negative":
                tips.append("Revise copy to have a more positive tone")
            
            return {
                "predicted_ctr": round(predicted_ctr * 100, 2),
                "predicted_ctr_raw": round(predicted_ctr, 4),
                "expected_impressions": int(expected_impressions),
                "expected_clicks": int(expected_clicks),
                "expected_conversions": int(expected_conversions),
                "text_analysis": {
                    "length": text_length,
                    "has_cta": has_call_to_action,
                    "sentiment": sentiment.get("sentiment"),
                    "sentiment_confidence": sentiment.get("confidence")
                },
                "optimization_tips": tips,
                "confidence": "medium" if len(tips) <= 2 else "low"
            }
            
        except Exception as e:
            logger.error(f"Ad performance prediction error: {e}")
            return {
                "predicted_ctr": 2.0,
                "optimization_tips": [],
                "error": str(e)
            }


# Singleton instance
ads_service = AdsService()
