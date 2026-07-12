from django.urls import path

from . import views
from .channels import MemoTrackingChannel, TestingChannel, VersionConsistencyChannel

urls = [
    path('src/<str:app>/<str:filename>', views.source),
]

websocket_urls = [
    path('ws/testing/', TestingChannel.as_asgi()),
    path('ws/testing/memo/', MemoTrackingChannel.as_asgi()),
    path('ws/testing/version/', VersionConsistencyChannel.as_asgi()),
]

urlpatterns = urls
