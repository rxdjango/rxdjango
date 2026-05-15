from django.urls import path

from .channels import NestedModelChannel

urls = []

websocket_urls = [
    path('ws/nested_model/', NestedModelChannel.as_asgi()),
]

urlpatterns = urls
