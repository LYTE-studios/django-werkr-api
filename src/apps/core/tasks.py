from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from celery.signals import task_failure
import logging
from django.utils.module_loading import import_string
from redis.exceptions import ConnectionError as RedisConnectionError

logger = logging.getLogger(__name__)

@task_failure.connect
def handle_task_failure(sender=None, task_id=None, exception=None, **kwargs):
    """Handle task failures and log them appropriately"""
    logger.error(f"Task {task_id} failed: {str(exception)}")

@shared_task(
    bind=True,
    max_retries=20,  # Increase max retries
    default_retry_delay=5,  # Start with a shorter delay
    autoretry_for=(RedisConnectionError,),  # Auto-retry for Redis connection errors
    retry_backoff=True,  # Enable exponential backoff
    retry_backoff_max=300,  # Maximum delay between retries (5 minutes)
    retry_jitter=True  # Add random jitter to prevent thundering herd
)
def execute_task(self, func_path, *args, **kwargs):
    """
    Execute a function as a Celery task with enhanced retry mechanism.
    
    Args:
        func_path (str): Import path to the function (e.g., 'apps.core.utils.my_function')
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
    """
    try:
        func = import_string(func_path)
        return func(*args, **kwargs)
    except RedisConnectionError as e:
        logger.warning(f"Redis connection lost for task {func_path}: {str(e)}")
        raise self.retry(exc=e)
    except Exception as e:
        logger.error(f"Error executing task {func_path}: {str(e)}")
        try:
            raise self.retry(exc=e)
        except MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for task {func_path}")
            raise e