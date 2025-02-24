# api/settings/production.py
from .base import *

DEBUG = False

CSRF_TRUSTED_ORIGINS = ['https://api.werkr.lytestudios.be']

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'production',
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT', cast=int, default=5432),
    }
}
