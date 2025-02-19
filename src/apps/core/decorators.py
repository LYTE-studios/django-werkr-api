from functools import wraps
import asyncio

def async_task(func):
    """
    Decorator to run a coroutine function as an asyncio task
    when called like a regular function.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not asyncio.iscoroutinefunction(func):
            raise ValueError("The decorated function must be a coroutine")
        
        try:
            # Try getting the current event loop
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # Possibly no event loop in the thread, so create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        if loop.is_running():
            # If the event loop is running, schedule the task
            return asyncio.create_task(func(*args, **kwargs))
        else:
            # If no event loop is running, start a new one and run the task
            return asyncio.run(func(*args, **kwargs))

    return wrapper
