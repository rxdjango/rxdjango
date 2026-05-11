"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

from testing import views as testing_views
from counter.channels import CounterChannel
from carousel.channels import CarouselChannel
from memo.channels import CarouselMemoChannel
from testing.channels import TestingChannel, MemoTrackingChannel
from authorization.channels import AuthorizationChannel
from authorization_meta.channels import AuthorizationMetaChannel

urlpatterns = [
    path('admin/', admin.site.urls),
    path('src/<str:app>/<str:filename>', testing_views.source),
]

websocket_urlpatterns = [
    path('ws/counter/', CounterChannel.as_asgi()),
    path('ws/carousel/', CarouselChannel.as_asgi()),
    path('ws/memo/', CarouselMemoChannel.as_asgi()),
    path('ws/testing/', TestingChannel.as_asgi()),
    path('ws/testing/memo/', MemoTrackingChannel.as_asgi()),
    path('ws/authorization/', AuthorizationChannel.as_asgi()),
    path('ws/authorization_meta/', AuthorizationMetaChannel.as_asgi()),
]
