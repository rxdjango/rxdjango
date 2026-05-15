from django.urls import path

from .channels import CounterChannel

urls = []

websocket_urls = [
    path('ws/counter/', CounterChannel.as_asgi()),
]

urlpatterns = urls
