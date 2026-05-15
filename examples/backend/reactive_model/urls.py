from django.urls import path

from .channels import ReactiveModelChannel

urls = []

websocket_urls = [
    path('ws/reactive_model/', ReactiveModelChannel.as_asgi()),
]

urlpatterns = urls
