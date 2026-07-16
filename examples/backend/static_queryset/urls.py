from django.urls import path

from .channels import StaticQuerysetChannel

urls = []

websocket_urls = [
    path('ws/static_queryset/', StaticQuerysetChannel.as_asgi()),
]

urlpatterns = urls
