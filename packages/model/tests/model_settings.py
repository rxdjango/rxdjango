"""Minimal Django settings for the package unit suites."""

SECRET_KEY = 'unit-tests'

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    # 'rxdjango_model' ahead of 'testapp' (app-population order) so its
    # models.py runs first, aliasing `rxdjango.models` before testapp's
    # models module imports `ReactiveModel` from it.
    'rxdjango',
    'rxdjango_model',
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
