"""
Celery configuration for background task processing
"""
from celery import Celery
from decouple import config
import logging

logger = logging.getLogger(__name__)

# Celery configuration
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default=REDIS_URL)
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default=REDIS_URL)

# Create Celery instance
celery_app = Celery('vexmail')

# Configure Celery
celery_app.conf.update(
    broker_url=CELERY_BROKER_URL,
    result_backend=CELERY_RESULT_BACKEND,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    task_routes={
        'vexmail.tasks.process_new_email': {'queue': 'email_processing'},
        'vexmail.tasks.sync_emails': {'queue': 'email_sync'},
        'vexmail.tasks.process_attachments': {'queue': 'attachments'},
        'vexmail.tasks.send_notification': {'queue': 'notifications'},
        'vexmail.tasks.cleanup_tasks': {'queue': 'cleanup'},
    },
    task_default_queue='default',
    task_queues={
        'default': {
            'exchange': 'default',
            'exchange_type': 'direct',
            'routing_key': 'default',
        },
        'email_processing': {
            'exchange': 'email_processing',
            'exchange_type': 'direct',
            'routing_key': 'email_processing',
        },
        'email_sync': {
            'exchange': 'email_sync',
            'exchange_type': 'direct',
            'routing_key': 'email_sync',
        },
        'attachments': {
            'exchange': 'attachments',
            'exchange_type': 'direct',
            'routing_key': 'attachments',
        },
        'notifications': {
            'exchange': 'notifications',
            'exchange_type': 'direct',
            'routing_key': 'notifications',
        },
        'cleanup': {
            'exchange': 'cleanup',
            'exchange_type': 'direct',
            'routing_key': 'cleanup',
        },
    },
    beat_schedule={
        'sync-emails-every-5-minutes': {
            'task': 'vexmail.tasks.periodic_email_sync',
            'schedule': 300.0,  # 5 minutes
        },
        'cleanup-failed-tasks': {
            'task': 'vexmail.tasks.cleanup_failed_tasks',
            'schedule': 3600.0,  # 1 hour
        },
        'process-pending-operations': {
            'task': 'vexmail.tasks.process_pending_operations',
            'schedule': 60.0,  # 1 minute
        },
    },
)

# Optional configuration for production
if config('CELERY_WORKER_CONCURRENCY', default=None):
    celery_app.conf.worker_concurrency = int(config('CELERY_WORKER_CONCURRENCY'))

if config('CELERY_MAX_TASKS_PER_CHILD', default=None):
    celery_app.conf.worker_max_tasks_per_child = int(config('CELERY_MAX_TASKS_PER_CHILD'))

logger.info("Celery configuration loaded successfully")
