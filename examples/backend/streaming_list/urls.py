from django.urls import path

from .channels import StreamingListChannel

urls = []

websocket_urls = [
    path('ws/streaming_list/', StreamingListChannel.as_asgi()),
]

urlpatterns = urls
