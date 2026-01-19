"""
Worker package - Celery tasks and configuration
"""
from kumele_ai.worker.celery_app import celery_app

__all__ = ["celery_app"]
