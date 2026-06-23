"""
ASGI Holystyl — HTTP + WebSocket (Channels).

Le routage WebSocket SCADA sera branché en Tranche 2 (app iot).
"""

import os

from channels.routing import ProtocolTypeRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        # "websocket": AuthMiddlewareStack(URLRouter(iot.routing.websocket_urlpatterns)),
    }
)
