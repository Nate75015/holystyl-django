"""Vues web analyses : laboratoire (rapports OCR), analyses de sol."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils.translation import gettext as _

from exploitations.models import Exploitation

from .models import AnalyseSol, AnalysisResult


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


@login_required
def laboratoire(request):
    exploitation = _exploitation(request)
    reports = AnalysisResult.objects.filter(exploitation=exploitation) if exploitation else AnalysisResult.objects.none()
    return render(request, "analyses/laboratoire.html", {"reports": reports, "page_title": _("Laboratoire")})


@login_required
def analyses_sol(request):
    exploitation = _exploitation(request)
    items = AnalyseSol.objects.filter(exploitation=exploitation) if exploitation else AnalyseSol.objects.none()
    return render(request, "analyses/analyses_sol.html", {"analyses": items, "page_title": _("Analyses de sol")})
