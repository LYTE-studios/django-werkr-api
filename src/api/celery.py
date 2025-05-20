import os
from celery import Celery
from kombu import Connection

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings.base')

app = Celery('api')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Configure Celery to handle Redis failover
app.conf.update(
    broker_transport_options={
        'retry_on_timeout': True,
        'max_retries': 3,
        'interval_start': 0,
        'interval_step': 1,
        'interval_max': 5,
    },
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    broker_connection_retry_on_startup=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Configure Redis connection pool
app.conf.broker_pool_limit = 3  # Number of connections to keep in the pool