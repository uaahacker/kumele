"""
Celery Tasks for async processing
"""
import logging
from typing import Optional, List, Dict, Any
from celery import shared_task
from kumele_ai.db.database import SessionLocal

logger = logging.getLogger(__name__)


def get_db_session():
    """Get database session for tasks"""
    return SessionLocal()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_knowledge_documents(self, document_ids: Optional[List[int]] = None):
    """
    Sync knowledge documents to Qdrant.
    
    - Chunks text (~500 tokens)
    - Generates embeddings
    - Upserts into Qdrant
    - Tracks version in Postgres
    """
    import asyncio
    from kumele_ai.services.chatbot_service import chatbot_service
    
    try:
        db = get_db_session()
        
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            chatbot_service.sync_documents(db, document_ids)
        )
        
        loop.close()
        db.close()
        
        logger.info(f"Document sync completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Document sync failed: {e}")
        self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def moderate_content(
    self,
    content_id: str,
    content_type: str,
    content_data: str,
    subtype: Optional[str] = None
):
    """
    Moderate content asynchronously.
    
    Supports text, image, and video content.
    """
    from kumele_ai.services.moderation_service import moderation_service
    
    try:
        db = get_db_session()
        
        if content_type == "text":
            result = moderation_service.moderate_text(
                db, content_data, subtype, content_id
            )
        elif content_type == "image":
            result = moderation_service.moderate_image(
                db, content_data, subtype, content_id
            )
        elif content_type == "video":
            # For video, content_data should be JSON with video_url and thumbnail_url
            import json
            video_data = json.loads(content_data)
            result = moderation_service.moderate_video(
                db,
                video_data.get("video_url"),
                video_data.get("thumbnail_url"),
                video_data.get("title"),
                video_data.get("description"),
                content_id
            )
        else:
            result = {"error": f"Unknown content type: {content_type}"}
        
        db.close()
        
        logger.info(f"Content moderation completed: {content_id}")
        return result
        
    except Exception as e:
        logger.error(f"Content moderation failed: {e}")
        self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_support_email(
    self,
    from_email: str,
    to_email: str,
    subject: str,
    body: str
):
    """
    Process incoming support email asynchronously.
    
    - Stores and cleans email
    - Classifies and analyzes sentiment
    - Generates AI response suggestion
    """
    import asyncio
    from kumele_ai.services.support_service import support_service
    
    try:
        db = get_db_session()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            support_service.process_incoming_email(
                db, from_email, to_email, subject, body
            )
        )
        
        loop.close()
        db.close()
        
        logger.info(f"Support email processed: {result.get('email_id')}")
        return result
        
    except Exception as e:
        logger.error(f"Support email processing failed: {e}")
        self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def generate_embeddings(self, texts: List[str], content_ids: Optional[List[str]] = None):
    """
    Generate embeddings for multiple texts.
    """
    from kumele_ai.services.embed_service import embed_service
    
    try:
        embeddings = embed_service.embed_texts(texts)
        
        result = {
            "count": len(embeddings),
            "dimension": len(embeddings[0]) if embeddings else 0
        }
        
        if content_ids:
            result["content_ids"] = content_ids
        
        logger.info(f"Generated {len(embeddings)} embeddings")
        return result
        
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def send_email_reply(
    self,
    email_id: int,
    response_text: str,
    response_type: str = "ai_generated"
):
    """
    Send email reply asynchronously.
    """
    import asyncio
    from kumele_ai.services.support_service import support_service
    
    try:
        db = get_db_session()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            support_service.send_reply(db, email_id, response_text, response_type)
        )
        
        loop.close()
        db.close()
        
        logger.info(f"Email reply sent: {result.get('reply_id')}")
        return result
        
    except Exception as e:
        logger.error(f"Email reply failed: {e}")
        self.retry(exc=e)


@shared_task(bind=True)
def calculate_host_ratings(self, host_ids: Optional[List[int]] = None):
    """
    Recalculate host ratings.
    """
    from kumele_ai.services.host_service import host_service
    from kumele_ai.db.models import User
    
    try:
        db = get_db_session()
        
        if host_ids:
            hosts = db.query(User).filter(User.id.in_(host_ids)).all()
        else:
            # Get all hosts (users who have hosted events)
            from kumele_ai.db.models import Event
            host_ids_query = db.query(Event.host_id).distinct().all()
            host_ids = [h[0] for h in host_ids_query]
            hosts = db.query(User).filter(User.id.in_(host_ids)).all()
        
        results = []
        for host in hosts:
            result = host_service.calculate_host_rating(db, host.id)
            results.append({
                "host_id": host.id,
                "score": result.get("overall_score")
            })
        
        db.close()
        
        logger.info(f"Calculated ratings for {len(results)} hosts")
        return {"hosts_updated": len(results), "results": results}
        
    except Exception as e:
        logger.error(f"Host rating calculation failed: {e}")
        raise


@shared_task(bind=True)
def update_reward_tiers(self, user_ids: Optional[List[int]] = None):
    """
    Update user reward tiers.
    """
    from kumele_ai.services.rewards_service import rewards_service
    from kumele_ai.db.models import User
    
    try:
        db = get_db_session()
        
        if user_ids:
            users = db.query(User).filter(User.id.in_(user_ids)).all()
        else:
            users = db.query(User).filter(User.is_active == True).all()
        
        results = []
        for user in users:
            suggestion = rewards_service.get_reward_suggestion(db, user.id)
            results.append({
                "user_id": user.id,
                "tier": suggestion.get("current_tier")
            })
        
        db.close()
        
        logger.info(f"Updated rewards for {len(results)} users")
        return {"users_updated": len(results)}
        
    except Exception as e:
        logger.error(f"Reward update failed: {e}")
        raise


@shared_task(bind=True)
def extract_keywords_batch(self, texts: List[Dict[str, str]]):
    """
    Extract keywords from multiple texts.
    
    texts: List of {"content_id": str, "text": str}
    """
    from kumele_ai.services.nlp_service import nlp_service
    
    try:
        db = get_db_session()
        
        results = []
        for item in texts:
            result = nlp_service.extract_keywords(
                db,
                item.get("text", ""),
                item.get("content_id")
            )
            results.append(result)
        
        db.close()
        
        logger.info(f"Extracted keywords from {len(results)} texts")
        return {"processed": len(results)}
        
    except Exception as e:
        logger.error(f"Keyword extraction failed: {e}")
        raise
