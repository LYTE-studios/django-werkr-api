from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def execute_task(self, func_path, *args, **kwargs):
    """
    Execute a function as a Celery task with retry mechanism.
    
    Args:
        func_path (str): Import path to the function (e.g., 'apps.core.utils.my_function')
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
    """
    from django.utils.module_loading import import_string
    
    try:
        func = import_string(func_path)
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Error executing task {func_path}: {str(e)}")
        try:
            # Retry the task with exponential backoff
            retry_delay = (2 ** self.request.retries) * 60  # 60s, 120s, 240s
            raise self.retry(exc=e, countdown=retry_delay)
        except MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for task {func_path}")
            raise e