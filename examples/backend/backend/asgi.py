"""
ASGI config for backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

app = get_asgi_application()

from backend.urls import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": app,
    "websocket": URLRouter(websocket_urlpatterns),
})
