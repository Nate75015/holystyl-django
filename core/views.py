"""Vues du socle : dashboard (Pulse) et endpoint de santé."""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from exploitations.models import Exploitation
from exploitations.services import compute_kpis


@login_required
def dashboard(request):
    """Écran Pulse : KPIs de l'exploitation courante."""
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    kpis = compute_kpis(exploitation)
    return render(
        request,
        "core/dashboard.html",
        {
            "page_title": "Pulse",
            "exploitation": exploitation,
            "needs_onboarding": exploitation is None,
            "kpis": kpis,
        },
    )


def healthz(request):
    """Sonde de disponibilité."""
    return JsonResponse({"app": "holystyl-django", "status": "ok"})
