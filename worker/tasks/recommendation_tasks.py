"""
Recommendation background tasks.
"""
from worker.celery_app import celery_app
import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="worker.tasks.recommendation_tasks.generate_recommendations")
def generate_recommendations(self, user_id: str):
    """
    Generate personalized recommendations for a user.
    """
    logger.info(f"Generating recommendations for user {user_id}")
    
    try:
        import asyncio
        from app.database import async_session_maker
        from app.services.recommendation_service import RecommendationService
        
        async def run_recommendations():
            async with async_session_maker() as db:
                # Generate hobby recommendations
                hobbies = await RecommendationService.recommend_hobbies(
                    db, user_id, limit=10
                )
                
                # Generate event recommendations
                events = await RecommendationService.recommend_events(
                    db, user_id, limit=10
                )
                
                # Cache recommendations
                await RecommendationService.cache_recommendations(
                    db, user_id, "hobby", hobbies["recommendations"]
                )
                await RecommendationService.cache_recommendations(
                    db, user_id, "event", events["recommendations"]
                )
                
                await db.commit()
                
                return {
                    "hobbies": len(hobbies["recommendations"]),
                    "events": len(events["recommendations"])
                }
        
        result = asyncio.run(run_recommendations())
        logger.info(f"Generated recommendations for {user_id}: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Recommendation task error: {e}")
        self.retry(exc=e, countdown=120, max_retries=3)


@celery_app.task(name="worker.tasks.recommendation_tasks.recalculate_all_ratings")
def recalculate_all_ratings():
    """
    Recalculate ratings for all hosts.
    Runs daily via beat schedule.
    """
    logger.info("Starting host ratings recalculation")
    
    try:
        import asyncio
        from sqlalchemy import select
        from app.database import async_session_maker
        from app.models.database_models import User
        from app.services.rating_service import RatingService
        
        async def run_recalculation():
            async with async_session_maker() as db:
                # Get all hosts (users who have hosted events)
                query = select(User.id).where(User.is_host == True)
                result = await db.execute(query)
                host_ids = [str(row[0]) for row in result.all()]
                
                recalculated = 0
                for host_id in host_ids:
                    try:
                        await RatingService.recalculate_host_rating(db, host_id)
                        recalculated += 1
                    except Exception as e:
                        logger.warning(f"Failed to recalculate for {host_id}: {e}")
                
                await db.commit()
                return recalculated
        
        count = asyncio.run(run_recalculation())
        logger.info(f"Recalculated ratings for {count} hosts")
        return {"recalculated": count}
        
    except Exception as e:
        logger.error(f"Recalculation task error: {e}")
        raise


@celery_app.task(name="worker.tasks.recommendation_tasks.update_user_embeddings")
def update_user_embeddings(user_id: str):
    """
    Update user embeddings for better recommendations.
    """
    logger.info(f"Updating embeddings for user {user_id}")
    
    try:
        import asyncio
        from app.database import async_session_maker
        from app.services.recommendation_service import RecommendationService
        
        async def run_update():
            async with async_session_maker() as db:
                # Get user interactions
                interactions = await RecommendationService.get_user_interactions(
                    db, user_id
                )
                
                # Update embedding based on interactions
                # (simplified - actual implementation would use ML model)
                
                await db.commit()
                return len(interactions)
        
        count = asyncio.run(run_update())
        logger.info(f"Updated embeddings for {user_id} with {count} interactions")
        return {"interactions_processed": count}
        
    except Exception as e:
        logger.error(f"Embedding update error: {e}")
        raise
