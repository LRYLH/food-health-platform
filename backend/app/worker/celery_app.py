"""
Celery is intentionally not enabled during local development.

The FastAPI analyze endpoints use BackgroundTasks so the project can run without
Docker, RabbitMQ, or Redis. When infrastructure is ready, configure Celery here
and replace the development background task with a queued task dispatch.
"""

celery_app = None
