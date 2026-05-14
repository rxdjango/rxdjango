from django.contrib import admin
from django.urls import path

<<<<<<< HEAD
from authorization import urls as authorization_urls
from authorization_meta import urls as authorization_meta_urls
from carousel import urls as carousel_urls
from counter import urls as counter_urls
from memo import urls as memo_urls
from nested_model import urls as nested_model_urls
from simple_model import urls as simple_model_urls
from testing import urls as testing_urls

APP_URLS = [
    counter_urls,
    carousel_urls,
    memo_urls,
    testing_urls,
    authorization_urls,
    authorization_meta_urls,
    simple_model_urls,
    nested_model_urls,
]

urls = [
    path('admin/', admin.site.urls),
]

<<<<<<< HEAD
for app_urls in APP_URLS:
    urls += app_urls.urls

websocket_urls = []
for app_urls in APP_URLS:
    websocket_urls += app_urls.websocket_urls

urlpatterns = urls
