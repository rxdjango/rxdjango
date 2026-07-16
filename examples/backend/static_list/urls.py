from django.urls import path

from .channels import StaticListChannel

urls = []

websocket_urls = [
    path('ws/static_list/', StaticListChannel.as_asgi()),
]

urlpatterns = urls
