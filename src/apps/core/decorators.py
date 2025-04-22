from functools import wraps
import asyncio

from asgiref.sync import async_to_sync
from django.core.signals import request_finished
from django.dispatch import receiver
import threading

def async_task(func):
    """
    Decorator to run a coroutine function as a background task
    without blocking the main thread. The task will be scheduled
    and executed asynchronously using Django's async utilities.
    
    This decorator is designed to work with Django applications
    and can be called from both sync and async contexts.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not asyncio.iscoroutinefunction(func):
            raise ValueError("The decorated function must be a coroutine")

        async def wrapped_task():
            try:
                await func(*args, **kwargs)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error in background task {func.__name__}: {str(e)}")

        def run_async_task():
            asyncio.run(wrapped_task())

        # Start the task in a separate thread
        thread = threading.Thread(target=run_async_task)
        thread.daemon = True  # Make the thread daemon so it won't block program exit
        thread.start()
        
        return None  # Return immediately, don't wait for the task

    return wrapper
