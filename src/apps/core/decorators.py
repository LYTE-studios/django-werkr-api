from functools import wraps
import inspect

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
        # Get the full import path of the decorated function
        module = func.__module__
        func_name = func.__name__
        func_path = f"{module}.{func_name}"
        
        # Schedule the task for execution
        execute_task.delay(func_path, *args, **kwargs)
        return None  # Return immediately, don't wait for the task
    
    return wrapper
