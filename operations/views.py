"""Vues web opérations : parc matériel, interventions terrain."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils.translation import gettext as _

from exploitations.models import Exploitation

from .models import Intervention, Machine


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


@login_required
def parc_materiel(request):
    exploitation = _exploitation(request)
    machines = Machine.objects.filter(exploitation=exploitation) if exploitation else Machine.objects.none()
    return render(request, "operations/parc_materiel.html", {"machines": machines, "page_title": _("Parc matériel")})


@login_required
def interventions(request):
    exploitation = _exploitation(request)
    items = Intervention.objects.filter(exploitation=exploitation) if exploitation else Intervention.objects.none()
    return render(request, "operations/interventions.html", {"interventions": items, "page_title": _("Interventions")})
