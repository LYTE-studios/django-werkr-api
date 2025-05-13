"""
ASGI config for api project.
"""

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings')

from django.core.asgi import get_asgi_application

# Handle lifespan events for ASGI servers
async def application(scope, receive, send):
    if scope['type'] == 'lifespan':
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                await send({'type': 'lifespan.startup.complete'})
            elif message['type'] == 'lifespan.shutdown':
                await send({'type': 'lifespan.shutdown.complete'})
                return
    return await get_asgi_application()(scope, receive, send)
