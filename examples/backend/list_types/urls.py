from django.urls import path

from .channels import ListTypesChannel

urls = []

websocket_urls = [
    path('ws/list_types/', ListTypesChannel.as_asgi()),
]

urlpatterns = urls
