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

# Link2Prisma settings
LINK2PRISMA_EMPLOYER_REF = '0719857388'  # Production employer reference

# Link2Prisma Settings
LINK2PRISMA_EMPLOYER_REF = '0719857388'  # Production employer reference
