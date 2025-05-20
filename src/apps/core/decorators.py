from functools import wraps
import inspect
import logging

logger = logging.getLogger(__name__)

def async_task(func):
    """
    Decorator to run a function as a background task using Celery.
    The task will be executed asynchronously in a Celery worker.
    
    This decorator works with regular synchronous functions and
    can be used in Django applications.
    
    Example:
        @async_task
        def send_email(user_id, subject, message):
            # Function implementation
            pass
    """
    from .tasks import execute_task
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Check if we're already in a Celery task
        frame = inspect.currentframe()
        while frame:
            if frame.f_code.co_name == 'execute_task':
                logger.info(f"[DEBUG] Already in Celery task, executing {func.__name__} directly")
                return func(*args, **kwargs)
            frame = frame.f_back

        # Get the full import path of the decorated function
        module = func.__module__
        func_name = func.__name__
        func_path = f"{module}.{func_name}"
        
        logger.info(f"[DEBUG] Creating new Celery task for {func_path}")
        # Schedule the task for execution
        task = execute_task.delay(func_path, *args, **kwargs)
        logger.info(f"[DEBUG] Created task with ID: {task.id}")
        return None  # Return immediately, don't wait for the task
    
    return wrapper
