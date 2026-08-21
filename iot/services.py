"""Diffusion temps réel SCADA (équivalent broadcastTelemetry de socket.io)."""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def group_name(exploitation_id: int) -> str:
    return f"scada_exploitation_{exploitation_id}"


def broadcast_telemetry(device, telemetry):
    """Pousse une mesure aux clients abonnés à l'exploitation du device."""
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        group_name(device.exploitation_id),
        {
            "type": "telemetry.message",
            "payload": {
                "event": "telemetry",
                "deviceId": device.id,
                "deviceName": device.name,
                "deviceType": device.device_type,
                "status": device.status,
                "flowRateM3h": telemetry.flow_rate_m3h,
                "pressureBar": telemetry.pressure_bar,
                "powerKw": telemetry.power_kw,
                "soilMoisture": telemetry.soil_moisture,
                "timestamp": telemetry.timestamp.isoformat() if telemetry.timestamp else None,
            },
        },
    )


def broadcast_device_status(device):
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        group_name(device.exploitation_id),
        {
            "type": "telemetry.message",
            "payload": {
                "event": "device_status",
                "deviceId": device.id,
                "deviceName": device.name,
                "status": device.status,
                "lastSeen": device.last_seen.isoformat() if device.last_seen else None,
            },
        },
    )


def alertes_ouvertes(exploitation, limite=5):
    """Les alertes non acquittées de l'exploitation (pour les tableaux de bord)."""
    if exploitation is None:
        return []
    from .models import IotAlert

    return list(IotAlert.objects.filter(exploitation=exploitation, acknowledged=False)[:limite])
