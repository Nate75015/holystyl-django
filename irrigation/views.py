"""Vues web irrigation : module Irrigation (onglets) et Bassinage."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils.translation import gettext as _

from exploitations.models import Exploitation

from .models import BassinageEvent, IrrigationProgram, IrrigationSession, IrrigationZone, PumpingStation


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


@login_required
def irrigation(request):
    exploitation = _exploitation(request)
    sessions = (
        list(IrrigationSession.objects.filter(exploitation=exploitation)[:20]) if exploitation else []
    )

    sessions_chart = None
    chrono = list(reversed(sessions))
    if any(s.volume_delivered_m3 for s in chrono):
        sessions_chart = {
            "labels": [s.start_time.strftime("%d/%m") for s in chrono],
            "data": [round(s.volume_delivered_m3 or 0, 1) for s in chrono],
            "color": "#0891b2",
            "label": "Volume (m³)",
        }

    ctx = {
        "page_title": _("Irrigation"),
        "tabs": [
            ("zones", _("Zones")),
            ("programs", _("Programmes")),
            ("sessions", _("Sessions")),
            ("stations", _("Stations")),
        ],
        "zones": IrrigationZone.objects.filter(exploitation=exploitation) if exploitation else [],
        "programs": IrrigationProgram.objects.filter(exploitation=exploitation) if exploitation else [],
        "sessions": sessions,
        "stations": PumpingStation.objects.filter(exploitation=exploitation) if exploitation else [],
        "sessions_chart": sessions_chart,
    }
    return render(request, "irrigation/irrigation.html", ctx)


@login_required
def bassinage(request):
    exploitation = _exploitation(request)
    events = (
        BassinageEvent.objects.filter(exploitation=exploitation) if exploitation else BassinageEvent.objects.none()
    )
    return render(request, "irrigation/bassinage.html", {"events": events, "page_title": _("Bassinage anti-gel")})
