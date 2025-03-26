from functools import wraps
import asyncio

<<<<<<< HEAD

def ensure_event_loop(func):
=======
def async_task(func):
    """
    Decorator to run a coroutine function as an asyncio task
    when called like a regular function.
    """

>>>>>>> main
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not asyncio.iscoroutinefunction(func):
            raise ValueError("The decorated function must be a coroutine")
        
        try:
            # Try getting the current event loop
            loop = asyncio.get_event_loop()
<<<<<<< HEAD
            # Check if the loop is running
            if not loop.is_running():
                # Create a new event loop if current one is not running
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

=======
>>>>>>> main
        except RuntimeError:
            # Possibly no event loop in the thread, so create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
<<<<<<< HEAD
        return func(*args, **kwargs, loop=loop)
=======
            
        if loop.is_running():
            # If the event loop is running, schedule the task
            return asyncio.create_task(func(*args, **kwargs))
        else:
            # If no event loop is running, start a new one and run the task
            return asyncio.run(func(*args, **kwargs))
>>>>>>> main

    return wrapper
