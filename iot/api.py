"""API DRF IoT (parité `iot.*`, `alerts.*`, `thresholds.*` tRPC)."""

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from exploitations.models import Exploitation

from .models import IotAlert, IotCommand, IotDevice, IotTelemetry, Threshold
from .serializers import (
    IotAlertSerializer,
    IotCommandSerializer,
    IotDeviceSerializer,
    IotTelemetrySerializer,
    ThresholdSerializer,
)


def current_exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


class IotDeviceViewSet(viewsets.ModelViewSet):
    serializer_class = IotDeviceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return IotDevice.objects.filter(exploitation=current_exploitation(self.request))

    def perform_create(self, serializer):
        exploitation = current_exploitation(self.request)
        if exploitation is None:
            raise ValidationError("Aucune exploitation.")
        serializer.save(exploitation=exploitation)

    @action(detail=True, methods=["get"])
    def telemetry(self, request, pk=None):
        device = self.get_object()
        limit = int(request.query_params.get("limit", 50))
        qs = device.telemetry.all()[:limit]
        return Response(IotTelemetrySerializer(qs, many=True).data)

    @action(detail=True, methods=["post"], url_path="send-command")
    def send_command(self, request, pk=None):
        device = self.get_object()
        command = IotCommand.objects.create(
            device=device,
            command_type=request.data.get("commandType", ""),
            parameters=request.data.get("parameters"),
            created_by=request.user,
        )
        return Response(IotCommandSerializer(command).data, status=status.HTTP_201_CREATED)


class IotAlertViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IotAlertSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return IotAlert.objects.filter(exploitation=current_exploitation(self.request))

    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        alert = self.get_object()
        alert.acknowledged = True
        alert.acknowledged_by = request.user
        alert.acknowledged_at = timezone.now()
        alert.save(update_fields=["acknowledged", "acknowledged_by", "acknowledged_at"])
        return Response(IotAlertSerializer(alert).data)


class ThresholdViewSet(viewsets.ModelViewSet):
    serializer_class = ThresholdSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Threshold.objects.filter(exploitation=current_exploitation(self.request))

    def perform_create(self, serializer):
        serializer.save(exploitation=current_exploitation(self.request))
