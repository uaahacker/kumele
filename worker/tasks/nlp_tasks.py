"""
NLP background tasks.
"""
from worker.celery_app import celery_app
import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="worker.tasks.nlp_tasks.analyze_content")
def analyze_content(self, content_id: str, text: str, content_type: str):
    """
    Analyze content for sentiment and keywords.
    """
    logger.info(f"Analyzing content {content_id}")
    
    try:
        import asyncio
        from app.database import async_session_maker
        from app.services.nlp_service import NLPService
        
        async def run_analysis():
            async with async_session_maker() as db:
                # Analyze sentiment
                sentiment = await NLPService.analyze_sentiment(text)
                
                # Store sentiment
                await NLPService.store_sentiment(
                    db, content_id, content_type,
                    sentiment["sentiment"], sentiment["score"]
                )
                
                # Extract keywords
                keywords = await NLPService.extract_keywords(text, max_keywords=10)
                
                # Update topic stats
                for kw in keywords.get("keywords", [])[:5]:
                    await NLPService.update_topic_daily(
                        db, kw["keyword"]
                    )
                
                await db.commit()
                
                return {
                    "sentiment": sentiment,
                    "keywords": len(keywords.get("keywords", []))
                }
        
        result = asyncio.run(run_analysis())
        logger.info(f"Analyzed content {content_id}: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Analysis task error: {e}")
        self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(name="worker.tasks.nlp_tasks.update_trending_topics")
def update_trending_topics():
    """
    Update trending topics aggregation.
    Runs hourly via beat schedule.
    """
    logger.info("Updating trending topics")
    
    try:
        import asyncio
        from datetime import datetime, timedelta
        from sqlalchemy import select, func, and_
        from app.database import async_session_maker
        from app.models.database_models import NLPKeyword, NLPTrend
        
        async def run_update():
            async with async_session_maker() as db:
                # Get keywords from last 24 hours
                since = datetime.utcnow() - timedelta(hours=24)
                
                query = select(
                    NLPKeyword.keyword,
                    func.count(NLPKeyword.id).label("count"),
                    func.avg(NLPKeyword.score).label("avg_score")
                ).where(
                    NLPKeyword.created_at >= since
                ).group_by(
                    NLPKeyword.keyword
                ).order_by(
                    func.count(NLPKeyword.id).desc()
                ).limit(100)
                
                result = await db.execute(query)
                trends = result.all()
                
                # Update or create trend records
                for keyword, count, avg_score in trends:
                    # Check existing
                    existing_query = select(NLPTrend).where(
                        and_(
                            NLPTrend.topic == keyword,
                            NLPTrend.date == datetime.utcnow().date()
                        )
                    )
                    existing_result = await db.execute(existing_query)
                    existing = existing_result.scalar_one_or_none()
                    
                    if existing:
                        existing.mention_count = count
                        existing.score = float(avg_score or 0)
                    else:
                        trend = NLPTrend(
                            topic=keyword,
                            date=datetime.utcnow().date(),
                            mention_count=count,
                            score=float(avg_score or 0)
                        )
                        db.add(trend)
                
                await db.commit()
                return len(trends)
        
        count = asyncio.run(run_update())
        logger.info(f"Updated {count} trending topics")
        return {"topics_updated": count}
        
    except Exception as e:
        logger.error(f"Trending update error: {e}")
        raise


@celery_app.task(name="worker.tasks.nlp_tasks.batch_analyze")
def batch_analyze(content_items: list):
    """
    Analyze multiple content items.
    """
    logger.info(f"Starting batch analysis for {len(content_items)} items")
    
    results = []
    for item in content_items:
        try:
            result = analyze_content.delay(
                content_id=item["content_id"],
                text=item["text"],
                content_type=item.get("content_type", "unknown")
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
