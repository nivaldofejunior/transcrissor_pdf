import os
from dotenv import load_dotenv
from celery import Celery

load_dotenv() 

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

print("[DEBUG] REDIS_URL:", REDIS_URL)

celery_app = Celery(
    "tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

from app.tasks import audio  # Isso importa e registra a task corretamente
