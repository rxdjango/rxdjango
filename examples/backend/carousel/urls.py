from django.urls import path

from .channels import CarouselChannel

urls = []

websocket_urls = [
    path('ws/carousel/', CarouselChannel.as_asgi()),
]

urlpatterns = urls
