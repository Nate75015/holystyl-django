"""Routage WebSocket de l'app iot."""

from django.urls import path

from .consumers import ScadaConsumer

websocket_urlpatterns = [
    path("ws/scada/", ScadaConsumer.as_asgi()),
]
