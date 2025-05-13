"""
ASGI config for api project.
"""

import os

print("Initializing ASGI application...")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings')

from django.core.asgi import get_asgi_application

# Get the ASGI application first
django_application = get_asgi_application()
print("Django application initialized")

# Then wrap it with lifespan handling
async def application(scope, receive, send):
    if scope['type'] == 'lifespan':
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                print("ASGI lifespan startup")
                await send({'type': 'lifespan.startup.complete'})
            elif message['type'] == 'lifespan.shutdown':
                print("ASGI lifespan shutdown")
                await send({'type': 'lifespan.shutdown.complete'})
                return
    return await django_application(scope, receive, send)
