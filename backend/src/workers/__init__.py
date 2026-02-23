"""Background worker tasks powered by Celery."""

from src.workers.celery_app import celery_app

__all__ = ["celery_app"]
