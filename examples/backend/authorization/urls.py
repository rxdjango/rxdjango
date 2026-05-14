from django.urls import path

from .channels import AuthorizationChannel

urls = []

websocket_urls = [
    path('ws/authorization/', AuthorizationChannel.as_asgi()),
]

urlpatterns = urls
