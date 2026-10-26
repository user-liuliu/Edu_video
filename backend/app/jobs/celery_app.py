from celery import Celery
from app.config import get_settings

settings = get_settings()
celery_app = Celery('edu_video', broker=settings.redis_url, include=['app.jobs.tasks','app.presentations.tasks'])
celery_app.conf.update(
    task_serializer='json', accept_content=['json'], result_serializer='json',
    task_ignore_result=True, task_acks_late=True, task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1, broker_connection_retry_on_startup=True,
    task_soft_time_limit=1700, task_time_limit=1800,
    beat_schedule={'recover-outbox':{'task':'edu.dispatch','schedule':15.0},'recover-ppt-outbox':{'task':'edu.ppt_dispatch','schedule':15.0}},
)
