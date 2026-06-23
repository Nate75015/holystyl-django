"""Consumer WebSocket SCADA (équivalent du namespace socket.io `/scada`)."""

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .services import group_name


class ScadaConsumer(AsyncJsonWebsocketConsumer):
    """Diffuse la télémétrie temps réel de l'exploitation de l'utilisateur connecté."""

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.exploitation_id = await self._user_exploitation_id(user)
        if self.exploitation_id is None:
            await self.close(code=4003)
            return

        self.group = group_name(self.exploitation_id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        # Snapshot initial des derniers relevés
        await self.send_json({"event": "connected", "exploitationId": self.exploitation_id})

    async def disconnect(self, code):
        if getattr(self, "group", None):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def telemetry_message(self, event):
        await self.send_json(event["payload"])

    @database_sync_to_async
    def _user_exploitation_id(self, user):
        from exploitations.models import Exploitation

        exploitation = Exploitation.objects.filter(owner=user).first()
        return exploitation.id if exploitation else None
