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
    exploitation = _exploitation(request)
    devices = IotDevice.objects.filter(exploitation=exploitation) if exploitation else IotDevice.objects.none()
    return render(request, "iot/capteurs.html", {"devices": devices, "page_title": _("Capteurs & IoT")})
