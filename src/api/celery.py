import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings.development')

# Create the Celery app
app = Celery('api')

# Configure Celery using Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load tasks from all registered Django app configs
app.autodiscover_tasks()

# Configure periodic tasks
app.conf.beat_schedule = {
    'sync-worker-data-daily': {
        'task': 'apps.legal.tasks.sync_worker_data',
        'schedule': crontab(hour=1, minute=0),  # Run at 1 AM every day
    },
}