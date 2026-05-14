from django.urls import path

from .channels import AuthorizationMetaChannel

urls = []

websocket_urls = [
    path('ws/authorization_meta/', AuthorizationMetaChannel.as_asgi()),
]

urlpatterns = urls
