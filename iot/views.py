"""Vues web IoT : Régie (SCADA temps réel) et Capteurs."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils.translation import gettext as _

from exploitations.models import Exploitation

from .models import IotAlert, IotDevice


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


@login_required
def regie(request):
    """Dashboard SCADA : devices + télémétrie temps réel (WebSocket)."""
    exploitation = _exploitation(request)
    devices = IotDevice.objects.filter(exploitation=exploitation) if exploitation else IotDevice.objects.none()
    alerts = (
        IotAlert.objects.filter(exploitation=exploitation, acknowledged=False)
        if exploitation else IotAlert.objects.none()
    )
    return render(
        request,
        "iot/regie.html",
        {"devices": devices, "alerts": alerts, "page_title": _("Régie SCADA")},
    )


@login_required
def capteurs(request):
    from .models import IotTelemetry

    exploitation = _exploitation(request)
    devices = IotDevice.objects.filter(exploitation=exploitation) if exploitation else IotDevice.objects.none()

    telemetry_chart = None
    if exploitation is not None:
        # Dernières mesures du device le plus actif (débit ou humidité)
        recent = list(
            IotTelemetry.objects.filter(device__exploitation=exploitation).order_by("-timestamp")[:30]
        )
        recent = list(reversed(recent))
        flows = [(t.timestamp, t.flow_rate_m3h) for t in recent if t.flow_rate_m3h is not None]
        soils = [(t.timestamp, t.soil_moisture) for t in recent if t.soil_moisture is not None]
        serie = flows or soils
        if serie:
            telemetry_chart = {
                "labels": [ts.strftime("%H:%M") if ts else "" for ts, _v in serie],
                "data": [round(v, 1) for _ts, v in serie],
                "color": "#2abfbf" if flows else "#22c55e",
                "label": "Débit (m³/h)" if flows else "Humidité (%)",
            }

    return render(
        request,
        "iot/capteurs.html",
        {"devices": devices, "telemetry_chart": telemetry_chart, "page_title": _("Capteurs & IoT")},
    )
