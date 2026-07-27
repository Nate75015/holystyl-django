"""Vues web PAC : suivi des aides PAC par campagne (KPIs, liste, ajout, suppression)."""

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from exploitations.models import Exploitation
from parcelles.models import ParcelleCampagne

from .models import AidePAC


def _to_float(value, default=None):
    try:
        return float(str(value).replace(",", ".").replace("€", "").replace(" ", "").strip())
    except (TypeError, ValueError):
        return default


def _libelles_campagnes(exploitation, base):
    """Campagnes proposées : celles des parcelles, celles déjà utilisées, la courante.

    La source de vérité reste la page « Campagnes » (Mes parcelles) ; on y ajoute
    les campagnes portant déjà une aide, pour ne jamais masquer de données.
    """
    libelles = set(base.values_list("campagne", flat=True))
    if exploitation:
        libelles |= set(
            ParcelleCampagne.objects
            .filter(parcelle__exploitation=exploitation)
            .values_list("libelle", flat=True)
        )
    libelles.discard("")
    libelles.add(ParcelleCampagne.libelle_courant())
    return sorted(libelles, reverse=True)


def _campagne(request, libelles):
    """Campagne affichée : ?campagne=… si connue, sinon la courante."""
    demandee = (request.GET.get("campagne") or "").strip()
    if demandee in libelles:
        return demandee
    courante = ParcelleCampagne.libelle_courant()
    return courante if courante in libelles else (libelles[0] if libelles else courante)


@login_required
def pac(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    base = AidePAC.objects.filter(exploitation=exploitation) if exploitation else AidePAC.objects.none()

    libelles = _libelles_campagnes(exploitation, base)
    campagne = _campagne(request, libelles)
    aides = base.filter(campagne=campagne)
    agg = aides.aggregate(total=Sum("montant"), surface=Sum("surface_ha"))
    paye = aides.filter(statut=AidePAC.Statut.PAYE).aggregate(s=Sum("montant"))["s"] or 0

    return render(request, "pac/pac.html", {
        "aides": aides,
        "libelles": libelles,
        "campagne": campagne,
        "kpi_total": round(agg["total"] or 0),
        "kpi_paye": round(paye),
        "kpi_surface": round(agg["surface"] or 0, 2),
        "kpi_count": aides.count(),
        "categories": AidePAC.Categorie.choices,
        "statuts": AidePAC.Statut.choices,
        "page_title": _("PAC"),
    })


@login_required
@require_POST
def pac_create(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    if exploitation:
        campagne = (request.POST.get("campagne") or "").strip() or ParcelleCampagne.libelle_courant()
        AidePAC.objects.create(
            exploitation=exploitation,
            campagne=campagne,
            categorie=request.POST.get("categorie") or AidePAC.Categorie.AUTRE,
            libelle=(request.POST.get("libelle") or "").strip(),
            montant=_to_float(request.POST.get("montant")),
            surface_ha=_to_float(request.POST.get("surface_ha")),
            statut=request.POST.get("statut") or AidePAC.Statut.PREVU,
        )
        return redirect(f"{reverse('pac:pac')}?campagne={campagne}")
    return redirect("pac:pac")


@login_required
@require_POST
def pac_delete(request, pk):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    aide = get_object_or_404(AidePAC, pk=pk, exploitation=exploitation)
    campagne = aide.campagne
    aide.delete()
    return redirect(f"{reverse('pac:pac')}?campagne={campagne}")
