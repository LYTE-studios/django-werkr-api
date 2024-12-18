"""
ASGI config for api project.
"""

import os
from decouple import config

# Set default environment to development
ENV = config('DJANGO_ENV', default='development')

# Set the Django settings module based on environment
if ENV == 'production':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings.production')
elif ENV == 'staging':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings.staging')
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings.development')

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
