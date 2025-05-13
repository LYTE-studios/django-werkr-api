"""
WSGI config for api project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os
import sys

print("Initializing WSGI application...", file=sys.stderr)

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

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
print("WSGI application initialized", file=sys.stderr)
