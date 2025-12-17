"""
Stream Service - Redis Streams scaffolding for near-real-time event processing

Provides event ingestion for:
- NLP trends (keyword extraction events)
- Ad impressions/clicks
- Activity signals (ratings, feedback, searches)

This enables moving from batch → near-real-time processing without redesign.
"""
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import redis
from kumele_ai.config import settings

logger = logging.getLogger(__name__)


class StreamService:
    """
    Redis Streams service for near-real-time event processing.
    
    Streams created:
    - nlp_events: NLP processing events (sentiment, keywords, trends)
    - ad_events: Ad impressions, clicks, conversions
    - activity_events: User activity signals
    - moderation_events: Content moderation events
    """
    
    # Stream names
    STREAM_NLP = "kumele:stream:nlp_events"
    STREAM_ADS = "kumele:stream:ad_events"
    STREAM_ACTIVITY = "kumele:stream:activity_events"
    STREAM_MODERATION = "kumele:stream:moderation_events"
    
    # Default retention (max entries per stream)
    DEFAULT_MAXLEN = 10000
    
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
    
    def _get_redis(self) -> redis.Redis:
        """Get Redis client"""
        if self._redis is None:
            self._redis = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True
            )
        return self._redis
    
    def _ensure_stream_exists(self, stream_name: str) -> bool:
        """Ensure stream exists by checking or creating"""
        try:
            r = self._get_redis()
            # Check if stream exists
            if not r.exists(stream_name):
                # Create stream with initial dummy entry (will be trimmed)
                r.xadd(
                    stream_name,
                    {"_init": "stream_created"},
                    maxlen=self.DEFAULT_MAXLEN
                )
                logger.info(f"Created Redis stream: {stream_name}")
            return True
        except Exception as e:
            logger.error(f"Error ensuring stream {stream_name}: {e}")
            return False
    
    def initialize_streams(self) -> Dict[str, bool]:
        """Initialize all required streams"""
        streams = [
            self.STREAM_NLP,
            self.STREAM_ADS,
            self.STREAM_ACTIVITY,
            self.STREAM_MODERATION
        ]
        
        results = {}
        for stream in streams:
            results[stream] = self._ensure_stream_exists(stream)
        
        return results
    
    def publish_event(
        self,
        stream_name: str,
        event_type: str,
        data: Dict[str, Any],
        maxlen: Optional[int] = None
    ) -> Optional[str]:
        """
        Publish event to a Redis stream.
        
        Args:
            stream_name: Target stream name
            event_type: Type of event (e.g., 'sentiment_analyzed', 'ad_clicked')
            data: Event payload
            maxlen: Optional max stream length (uses default if not specified)
            
        Returns:
            Stream entry ID or None on failure
        """
        try:
            r = self._get_redis()
            
            # Prepare event data
            event = {
                "type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "data": json.dumps(data)
            }
            
            # Add to stream with retention policy
            entry_id = r.xadd(
                stream_name,
                event,
                maxlen=maxlen or self.DEFAULT_MAXLEN,
                approximate=True  # Better performance
            )
            
            logger.debug(f"Published event to {stream_name}: {event_type}")
            return entry_id
            
        except Exception as e:
            logger.error(f"Error publishing to stream {stream_name}: {e}")
            return None
    
    # ==========================================
    # NLP Events
    # ==========================================
    
    def publish_sentiment_event(
        self,
        content_id: str,
        content_type: str,
        sentiment: str,
        confidence: float,
        user_id: Optional[int] = None
    ) -> Optional[str]:
        """Publish sentiment analysis event"""
        return self.publish_event(
            self.STREAM_NLP,
            "sentiment_analyzed",
            {
                "content_id": content_id,
                "content_type": content_type,
                "sentiment": sentiment,
                "confidence": confidence,
                "user_id": user_id
            }
        )
    
    def publish_keywords_event(
        self,
        content_id: str,
        keywords: List[str],
        entities: List[str],
        user_id: Optional[int] = None
    ) -> Optional[str]:
        """Publish keyword extraction event"""
        return self.publish_event(
            self.STREAM_NLP,
            "keywords_extracted",
            {
                "content_id": content_id,
                "keywords": keywords,
                "entities": entities,
                "user_id": user_id
            }
        )
    
    # ==========================================
    # Ad Events
    # ==========================================
    
    def publish_ad_impression(
        self,
        ad_id: int,
        user_id: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Publish ad impression event"""
        return self.publish_event(
            self.STREAM_ADS,
            "ad_impression",
            {
                "ad_id": ad_id,
                "user_id": user_id,
                "context": context or {}
            }
        )
    
    def publish_ad_click(
        self,
        ad_id: int,
        user_id: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Publish ad click event"""
        return self.publish_event(
            self.STREAM_ADS,
            "ad_click",
            {
                "ad_id": ad_id,
                "user_id": user_id,
                "context": context or {}
            }
        )
    
    def publish_ad_conversion(
        self,
        ad_id: int,
        user_id: int,
        conversion_type: str,
        value: Optional[float] = None
    ) -> Optional[str]:
        """Publish ad conversion event"""
        return self.publish_event(
            self.STREAM_ADS,
            "ad_conversion",
            {
                "ad_id": ad_id,
                "user_id": user_id,
                "conversion_type": conversion_type,
                "value": value
            }
        )
    
    # ==========================================
    # Activity Events
    # ==========================================
    
    def publish_activity_event(
        self,
        user_id: int,
        activity_type: str,
        entity_type: str,
        entity_id: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Publish user activity event"""
        return self.publish_event(
            self.STREAM_ACTIVITY,
            activity_type,
            {
                "user_id": user_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "metadata": metadata or {}
            }
        )
    
    def publish_rating_event(
        self,
        user_id: int,
        event_id: int,
        rating: float,
        feedback: Optional[str] = None
    ) -> Optional[str]:
        """Publish rating event"""
        return self.publish_event(
            self.STREAM_ACTIVITY,
            "rating_submitted",
            {
                "user_id": user_id,
                "event_id": event_id,
                "rating": rating,
                "feedback": feedback
            }
        )
    
    def publish_search_event(
        self,
        user_id: Optional[int],
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        results_count: int = 0
    ) -> Optional[str]:
        """Publish search event"""
        return self.publish_event(
            self.STREAM_ACTIVITY,
            "search_performed",
            {
                "user_id": user_id,
                "query": query,
                "filters": filters or {},
                "results_count": results_count
            }
        )
    
    # ==========================================
    # Moderation Events
    # ==========================================
    
    def publish_moderation_event(
        self,
        content_id: str,
        content_type: str,
        decision: str,
        labels: Dict[str, Any],
        user_id: Optional[int] = None
    ) -> Optional[str]:
        """Publish moderation event"""
        return self.publish_event(
            self.STREAM_MODERATION,
            "content_moderated",
            {
                "content_id": content_id,
                "content_type": content_type,
                "decision": decision,
                "labels": labels,
                "user_id": user_id
            }
        )
    
    # ==========================================
    # Stream Reading (for consumers)
    # ==========================================
    
    def read_events(
        self,
        stream_name: str,
        count: int = 100,
        last_id: str = "0"
    ) -> List[Dict[str, Any]]:
        """
        Read events from stream (for consumer processing).
        
        Args:
            stream_name: Stream to read from
            count: Max events to read
            last_id: Read events after this ID ("0" for all, "$" for new only)
            
        Returns:
            List of events with their IDs
        """
        try:
            r = self._get_redis()
            
            events = r.xrange(stream_name, min=last_id, count=count)
            
            result = []
            for entry_id, data in events:
                event = {
                    "id": entry_id,
                    "type": data.get("type"),
                    "timestamp": data.get("timestamp"),
                    "data": json.loads(data.get("data", "{}"))
                }
                result.append(event)
            
            return result
            
        except Exception as e:
            logger.error(f"Error reading from stream {stream_name}: {e}")
            return []
    
    def get_stream_info(self, stream_name: str) -> Dict[str, Any]:
        """Get stream information"""
        try:
            r = self._get_redis()
            info = r.xinfo_stream(stream_name)
            return {
                "length": info.get("length", 0),
                "first_entry": info.get("first-entry"),
                "last_entry": info.get("last-entry"),
                "groups": info.get("groups", 0)
            }
        except Exception as e:
            logger.error(f"Error getting stream info: {e}")
            return {"error": str(e)}
    
    def get_all_streams_info(self) -> Dict[str, Any]:
        """Get info for all managed streams"""
        streams = [
            self.STREAM_NLP,
            self.STREAM_ADS,
            self.STREAM_ACTIVITY,
            self.STREAM_MODERATION
        ]
        
        return {
            stream: self.get_stream_info(stream)
            for stream in streams
        }


# Singleton instance
stream_service = StreamService()
