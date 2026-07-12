"""Minimal Django settings for the package unit suites."""

SECRET_KEY = 'unit-tests'

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'testapp',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
