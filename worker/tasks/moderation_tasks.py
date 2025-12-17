"""
Moderation background tasks.
"""
from worker.celery_app import celery_app
import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="worker.tasks.moderation_tasks.moderate_content_async")
def moderate_content_async(self, content_id: str, content_type: str, content: str):
    """
    Asynchronously moderate content.
    Used for non-blocking moderation of large content.
    """
    logger.info(f"Starting async moderation for {content_id}")
    
    try:
        # Import here to avoid circular imports
        import asyncio
        from app.database import async_session_maker
        from app.services.moderation_service import ModerationService
        
        async def run_moderation():
            async with async_session_maker() as db:
                result = await ModerationService.moderate_content(
                    db=db,
                    content_id=content_id,
                    content_type=content_type,
                    text=content if content_type == "text" else None,
                    image_url=content if content_type == "image" else None,
                    video_url=content if content_type == "video" else None
                )
                await db.commit()
                return result
        
        result = asyncio.run(run_moderation())
        logger.info(f"Completed moderation for {content_id}: {result.get('decision')}")
        return result
        
    except Exception as e:
        logger.error(f"Moderation task error: {e}")
        self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(name="worker.tasks.moderation_tasks.cleanup_old_jobs")
def cleanup_old_jobs():
    """
    Clean up old moderation jobs.
    Runs daily via beat schedule.
    """
    logger.info("Starting moderation jobs cleanup")
    
    try:
        import asyncio
        from datetime import datetime, timedelta
        from sqlalchemy import delete
        from app.database import async_session_maker
        from app.models.database_models import ModerationJob
        
        async def run_cleanup():
            async with async_session_maker() as db:
                cutoff = datetime.utcnow() - timedelta(days=90)
                
                query = delete(ModerationJob).where(
                    ModerationJob.created_at < cutoff
                )
                
                result = await db.execute(query)
                await db.commit()
                return result.rowcount
        
        deleted = asyncio.run(run_cleanup())
        logger.info(f"Deleted {deleted} old moderation jobs")
        return {"deleted": deleted}
        
    except Exception as e:
        logger.error(f"Cleanup task error: {e}")
        raise


@celery_app.task(name="worker.tasks.moderation_tasks.batch_moderate")
def batch_moderate(content_items: list):
    """
    Moderate multiple content items in batch.
    """
    logger.info(f"Starting batch moderation for {len(content_items)} items")
    
    results = []
    for item in content_items:
        try:
            result = moderate_content_async.delay(
                content_id=item["content_id"],
                content_type=item["content_type"],
                content=item["content"]
            )
            results.append({
                "content_id": item["content_id"],
                "task_id": result.id
            })
        except Exception as e:
            logger.error(f"Batch item error: {e}")
            results.append({
                "content_id": item["content_id"],
                "error": str(e)
            })
    
    return results
