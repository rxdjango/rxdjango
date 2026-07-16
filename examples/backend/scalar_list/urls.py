from django.urls import path

from .channels import ScalarListChannel

urls = []

websocket_urls = [
    path('ws/scalar_list/', ScalarListChannel.as_asgi()),
]

urlpatterns = urls
