# Load different settings based on environment
from decouple import config

ENV = config('DJANGO_ENV', default='staging')

if ENV == 'production':
    print('STARTED PRODUCTION')
    from .production import *
elif ENV == 'staging':
    print('STARTED STAGING')
    from .staging import *
else:
    print('STARTED DEVELOPMENT')
    from .development import *