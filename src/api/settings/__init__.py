# Load different settings based on environment
import os
from decouple import Config, RepositoryEnv

# Get the absolute path to the .env file
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
config = Config(RepositoryEnv(env_path))

print(f"Looking for .env file at: {env_path}")
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