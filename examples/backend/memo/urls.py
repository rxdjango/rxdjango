from django.urls import path

from .channels import CarouselMemoChannel

urls = []

websocket_urls = [
    path('ws/memo/', CarouselMemoChannel.as_asgi()),
]

urlpatterns = urls
