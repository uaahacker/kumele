"""
Celery Application Configuration
"""
from celery import Celery
from kumele_ai.config import settings

# Create Celery app
celery_app = Celery(
    "kumele_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "kumele_ai.worker.tasks"
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
    task_time_limit=600,  # 10 minutes max
    task_soft_time_limit=540,  # 9 minutes soft limit
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    result_expires=3600,  # Results expire after 1 hour
)

# Task routing
celery_app.conf.task_routes = {
    "kumele_ai.worker.tasks.sync_knowledge_documents": {"queue": "knowledge"},
    "kumele_ai.worker.tasks.moderate_content": {"queue": "moderation"},
    "kumele_ai.worker.tasks.process_support_email": {"queue": "support"},
    "kumele_ai.worker.tasks.generate_embeddings": {"queue": "embeddings"},
    "kumele_ai.worker.tasks.*": {"queue": "default"},
}
