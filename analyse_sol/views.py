"""Vues web analyses de sol."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils.translation import gettext as _

from exploitations.models import Exploitation

from .models import AnalyseSol


@login_required
def analyses_sol(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    items = AnalyseSol.objects.filter(exploitation=exploitation) if exploitation else AnalyseSol.objects.none()
    return render(request, "analyse_sol/analyses_sol.html", {"analyses": items, "page_title": _("Analyses de sol")})
