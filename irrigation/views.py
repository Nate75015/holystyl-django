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
        "sessions": (
            IrrigationSession.objects.filter(exploitation=exploitation)[:20] if exploitation else []
        ),
        "stations": PumpingStation.objects.filter(exploitation=exploitation) if exploitation else [],
    }
    return render(request, "irrigation/irrigation.html", ctx)


@login_required
def bassinage(request):
    exploitation = _exploitation(request)
    events = (
        BassinageEvent.objects.filter(exploitation=exploitation) if exploitation else BassinageEvent.objects.none()
    )
    return render(request, "irrigation/bassinage.html", {"events": events, "page_title": _("Bassinage anti-gel")})
