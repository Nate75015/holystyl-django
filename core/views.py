"""Vues du socle : dashboard (Pulse) et endpoint de santé."""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render


@login_required
def dashboard(request):
    """Écran Pulse (placeholder de socle — enrichi en Tranche 1)."""
    return render(request, "core/dashboard.html", {"page_title": "Pulse"})


def healthz(request):
    """Sonde de disponibilité."""
    return JsonResponse({"app": "holystyl-django", "status": "ok"})
