# api/settings/staging.py
from .base import *

DEBUG = config('DEBUG', default=False, cast=bool)

# Add this line to include your trusted origin
CSRF_TRUSTED_ORIGINS = ['https://staging.api.werkr.lytestudios.be']

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'staging',
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT', cast=int, default=5432),
    }
}

# Link2Prisma settings
LINK2PRISMA_EMPLOYER_REF = 'test_employer_ref'  # Test reference for staging environment

# Link2Prisma Settings
LINK2PRISMA_EMPLOYER_REF = '999014'  # Test reference for staging environment