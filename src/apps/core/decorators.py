from functools import wraps
import asyncio

def async_task(func):
    """
    Decorator to run a coroutine function as a background task
    without blocking the main thread. The task will be scheduled
    on the event loop and executed asynchronously.
    
    This decorator is designed to work with ASGI applications
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
                raise

        try:
            # Try to get the running loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # If no loop is running, create a new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Create and schedule the task
            loop.create_task(wrapped_task())
            return None  # Return immediately, don't wait for the task
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error scheduling background task: {str(e)}")
            raise

    return wrapper
