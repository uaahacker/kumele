"""
Celery worker configuration for background tasks.
"""
from celery import Celery
from app.config import settings

# Create Celery app
celery_app = Celery(
    "kumele_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "worker.tasks.moderation_tasks",
        "worker.tasks.recommendation_tasks",
        "worker.tasks.nlp_tasks",
        "worker.tasks.email_tasks",
    ]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Task routes
    task_routes={
        "worker.tasks.moderation_tasks.*": {"queue": "moderation"},
        "worker.tasks.recommendation_tasks.*": {"queue": "recommendations"},
        "worker.tasks.nlp_tasks.*": {"queue": "nlp"},
        "worker.tasks.email_tasks.*": {"queue": "email"},
    },
    
    # Beat schedule for periodic tasks
    beat_schedule={
        "update-trending-topics": {
            "task": "worker.tasks.nlp_tasks.update_trending_topics",
            "schedule": 3600.0,  # Every hour
        },
        "recalculate-host-ratings": {
            "task": "worker.tasks.recommendation_tasks.recalculate_all_ratings",
            "schedule": 86400.0,  # Daily
        },
        "cleanup-old-moderation-jobs": {
            "task": "worker.tasks.moderation_tasks.cleanup_old_jobs",
            "schedule": 86400.0,  # Daily
        },
    }
)

if __name__ == "__main__":
    celery_app.start()
