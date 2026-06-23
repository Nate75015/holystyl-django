"""Vues du socle : dashboard (Pulse) et endpoint de santé."""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from exploitations.models import Exploitation
from exploitations.services import compute_kpis


def _reversed(qs):
    return list(reversed(list(qs)))


@login_required
def dashboard(request):
    """Écran Pulse : jauge DTI, météo, alertes et graphiques de l'exploitation."""
    from iot.models import IotAlert
    from irrigation.models import DtiScore, WaterMeter

    exploitation = Exploitation.objects.filter(owner=request.user).first()
    kpis = compute_kpis(exploitation)

    dti = None
    dti_chart = None
    water_chart = None
    alerts = []

    if exploitation is not None:
        dti = DtiScore.objects.filter(exploitation=exploitation).first()

        history = _reversed(DtiScore.objects.filter(exploitation=exploitation)[:14])
        if history:
            dti_chart = {
                "labels": [d.calculated_at.strftime("%d/%m") for d in history],
                "data": [round(d.score_numeric, 1) for d in history],
                "color": "#0891b2",
                "label": "Score DTI",
            }

        meters = _reversed(WaterMeter.objects.filter(exploitation=exploitation)[:14])
        if meters:
            water_chart = {
                "labels": [m.reading_date.strftime("%d/%m") for m in meters],
                "data": [round(m.volume_m3, 1) for m in meters],
                "color": "#22c55e",
                "label": "Volume eau (m³)",
            }

        alerts = IotAlert.objects.filter(exploitation=exploitation, acknowledged=False)[:5]

    return render(
        request,
        "core/dashboard.html",
        {
            "page_title": "Tableau de bord",
            "exploitation": exploitation,
            "needs_onboarding": exploitation is None,
            "kpis": kpis,
            "dti": dti,
            "dti_chart": dti_chart,
            "water_chart": water_chart,
            "alerts": alerts,
        },
    )


def healthz(request):
    """Sonde de disponibilité."""
    return JsonResponse({"app": "holystyl-django", "status": "ok"})
