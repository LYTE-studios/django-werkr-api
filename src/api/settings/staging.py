# api/settings/staging.py
from .production import *

DEBUG = config('DEBUG', default=False, cast=bool)

# Less strict security settings for staging
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
