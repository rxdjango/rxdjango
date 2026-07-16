from django.urls import path

from .channels import TaskBoardChannel

urls = []

websocket_urls = [
    path('ws/task_board/', TaskBoardChannel.as_asgi()),
]

urlpatterns = urls
