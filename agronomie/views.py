"""Vues web agronomie : référentiels cultures Kc / types de sol, saisons."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils.translation import gettext as _

from exploitations.models import Exploitation

from .models import CultureKc, Saison, TypeSol


@login_required
def cultures_kc(request):
    return render(
        request,
        "agronomie/cultures_kc.html",
        {"cultures": CultureKc.objects.all(), "page_title": _("Cultures & Kc")},
    )


@login_required
def types_sol(request):
    return render(
        request,
        "agronomie/types_sol.html",
        {"types": TypeSol.objects.all(), "page_title": _("Types de sol")},
    )


@login_required
def saisons(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    qs = Saison.objects.filter(exploitation=exploitation) if exploitation else Saison.objects.none()
    return render(request, "agronomie/saisons.html", {"saisons": qs, "page_title": _("Saisons")})
