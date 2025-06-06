"""
ASGI config for api project.
"""

import os
import sys
import traceback

try:
    print("Initializing ASGI application...", file=sys.stderr)
    print(f"Current working directory: {os.getcwd()}", file=sys.stderr)
    print(f"PYTHONPATH: {sys.path}", file=sys.stderr)
    
    # Force remove any existing DJANGO_SETTINGS_MODULE
    if 'DJANGO_SETTINGS_MODULE' in os.environ:
        print(f"Removing existing DJANGO_SETTINGS_MODULE: {os.environ['DJANGO_SETTINGS_MODULE']}", file=sys.stderr)
        del os.environ['DJANGO_SETTINGS_MODULE']
    
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings')
    print(f"Settings module set to: {os.environ['DJANGO_SETTINGS_MODULE']}", file=sys.stderr)
    
    # Import settings to trigger initialization
    print("Importing settings...", file=sys.stderr)
    from api import settings
    print("Settings imported", file=sys.stderr)
    
    from django.core.asgi import get_asgi_application
    
    # Get the ASGI application first
    print("Getting Django application...", file=sys.stderr)
    django_application = get_asgi_application()
    print("Django application initialized successfully", file=sys.stderr)

except Exception as e:
    print("Error during ASGI initialization:", file=sys.stderr)
    print(str(e), file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    raise

# Then wrap it with lifespan handling
async def application(scope, receive, send):
    try:
        if scope['type'] == 'lifespan':
            while True:
                message = await receive()
                if message['type'] == 'lifespan.startup':
                    print("ASGI lifespan startup", file=sys.stderr)
                    await send({'type': 'lifespan.startup.complete'})
                elif message['type'] == 'lifespan.shutdown':
                    print("ASGI lifespan shutdown", file=sys.stderr)
                    await send({'type': 'lifespan.shutdown.complete'})
                    return
        return await django_application(scope, receive, send)
    except Exception as e:
        print(f"Error in ASGI application: {str(e)}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise
