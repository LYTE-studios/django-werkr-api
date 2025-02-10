# api/settings/__init__.py
from .base import *

# Load different settings based on environment
from decouple import config

ENV = config("DJANGO_ENV", default="development")

if ENV == "production":
    from .production import *
elif ENV == "staging":
    from .staging import *
else:
    from .development import *
