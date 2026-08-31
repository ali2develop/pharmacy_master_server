import os
from .base import *

DEBUG = True

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-%x3g5dex3-zkhir8^sdrl_n%z)-iaxhfw70uc(azw#y_!zt1tm')

ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
