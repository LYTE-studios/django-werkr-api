from functools import wraps
import asyncio

def async_task(func):
    """
    Decorator to run a coroutine function as a background task
    without blocking the main thread. The task will be scheduled
    on the event loop and executed asynchronously.
    
    This decorator is designed to work with ASGI applications
    and expects to be running in an async context.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
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
            # Get the running loop (will raise RuntimeError if no loop is running)
            loop = asyncio.get_running_loop()
            # Create and schedule the task
            task = loop.create_task(wrapped_task())
            return None  # Return immediately, don't wait for the task
        except RuntimeError as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"No running event loop available: {str(e)}")
            raise

    return wrapper
