from functools import wraps
import asyncio


def ensure_event_loop(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_event_loop()
            # Check if the loop is running
            if not loop.is_running():
                # Create a new event loop if current one is not running
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return func(*args, **kwargs, loop=loop)

    return wrapper
