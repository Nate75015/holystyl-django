"""Vues web finances : charges, revenus, bilan économique, facturation."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils.translation import gettext as _

from exploitations.models import Exploitation

from .models import Charge, Facture, Revenu
from .services import compute_bilan


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


@login_required
def charges(request):
    exploitation = _exploitation(request)
    items = Charge.objects.filter(exploitation=exploitation) if exploitation else Charge.objects.none()
    return render(request, "finances/charges.html", {"charges": items, "page_title": _("Charges")})


@login_required
def bilan_economique(request):
    exploitation = _exploitation(request)
    bilan = compute_bilan(exploitation)
    revenus = Revenu.objects.filter(exploitation=exploitation) if exploitation else Revenu.objects.none()
    return render(
        request,
        "finances/bilan_economique.html",
        {"bilan": bilan, "revenus": revenus, "page_title": _("Bilan économique")},
    )


@login_required
def facturation(request):
    exploitation = _exploitation(request)
    factures = Facture.objects.filter(exploitation=exploitation) if exploitation else Facture.objects.none()
    return render(request, "finances/facturation.html", {"factures": factures, "page_title": _("Facturation")})
