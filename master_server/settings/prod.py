import os
from django.core.exceptions import ImproperlyConfigured
from .base import *

DEBUG = False

# Ensure SECRET_KEY is provided via environment
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY environment variable is not set!")

# The username will be filled in by the deployment script or user on PythonAnywhere
ALLOWED_HOSTS = ['REPLACE_WITH_MY_USERNAME.pythonanywhere.com']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
