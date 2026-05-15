from django.urls import path

from .channels import SimpleModelChannel

urls = []

websocket_urls = [
    path('ws/simple_model/', SimpleModelChannel.as_asgi()),
]

urlpatterns = urls
