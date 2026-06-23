"""Endpoints REST pour les gateways IoT (LoRa/4G) — sans session utilisateur.

Parité avec les routes Express :
  POST /api/iot/ingest            (télémétrie)
  GET  /api/iot/command/poll      (commandes en attente)
  POST /api/iot/command/callback  (ACK exécution)

Authentification par `deviceToken` (corps JSON ou header X-Device-Token).
"""

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import IotCommand, IotDevice, IotTelemetry
from .services import broadcast_device_status, broadcast_telemetry


def _device_from_token(request):
    token = request.headers.get("X-Device-Token") or request.data.get("deviceToken") or request.query_params.get("token")
    if not token:
        return None
    return IotDevice.objects.filter(device_token=token).first()


class IotIngestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        device = _device_from_token(request)
        if device is None:
            return Response({"error": "invalid device token"}, status=status.HTTP_401_UNAUTHORIZED)

        data = request.data
        telemetry = IotTelemetry.objects.create(
            device=device,
            timestamp=timezone.now(),
            payload=data.get("payload"),
            primary_value=data.get("primaryValue"),
            primary_unit=data.get("primaryUnit", ""),
            flow_rate_m3h=data.get("flowRateM3h"),
            pressure_bar=data.get("pressureBar"),
            power_kw=data.get("powerKw"),
            energy_kwh=data.get("energyKwh"),
            soil_moisture=data.get("soilMoisture"),
            signal_strength=data.get("signalStrength"),
            battery_level=data.get("batteryLevel"),
        )
        device.last_seen = timezone.now()
        device.status = IotDevice.Status.ONLINE
        device.save(update_fields=["last_seen", "status"])

        broadcast_telemetry(device, telemetry)
        return Response({"ok": True, "telemetryId": telemetry.id}, status=status.HTTP_201_CREATED)


class IotCommandPollView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        device = _device_from_token(request)
        if device is None:
            return Response({"error": "invalid device token"}, status=status.HTTP_401_UNAUTHORIZED)

        pending = list(device.commands.filter(status=IotCommand.Status.PENDING))
        now = timezone.now()
        for cmd in pending:
            cmd.status = IotCommand.Status.SENT
            cmd.sent_at = now
            cmd.save(update_fields=["status", "sent_at"])

        return Response(
            {
                "commands": [
                    {"id": c.id, "commandType": c.command_type, "parameters": c.parameters}
                    for c in pending
                ]
            }
        )


class IotCommandCallbackView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        device = _device_from_token(request)
        if device is None:
            return Response({"error": "invalid device token"}, status=status.HTTP_401_UNAUTHORIZED)

        command_id = request.data.get("commandId")
        new_status = request.data.get("status", IotCommand.Status.COMPLETED)
        command = IotCommand.objects.filter(id=command_id, device=device).first()
        if command is None:
            return Response({"error": "command not found"}, status=status.HTTP_404_NOT_FOUND)

        command.status = new_status
        now = timezone.now()
        if new_status == IotCommand.Status.ACKNOWLEDGED:
            command.acknowledged_at = now
        elif new_status in (IotCommand.Status.COMPLETED, IotCommand.Status.FAILED):
            command.completed_at = now
        command.save()

        broadcast_device_status(device)
        return Response({"ok": True})
