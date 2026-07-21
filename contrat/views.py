"""Vues web Contrats : liste, KPIs, ajout et suppression (tenant-scoped)."""

from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from exploitations.models import Exploitation

from .models import ActeNotarie, Assurance, Bail, Contrat


def _to_float(value, default=None):
    try:
        return float(str(value).replace(",", ".").replace("€", "").replace(" ", "").strip())
    except (TypeError, ValueError):
        return default


def _to_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


@login_required
def contrats(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    base = Contrat.objects.filter(exploitation=exploitation) if exploitation else Contrat.objects.none()

    total = base.aggregate(s=Sum("montant"))["s"] or 0
    nb_actifs = base.filter(statut=Contrat.Statut.ACTIF).count()

    return render(request, "contrat/contrats.html", {
        "contrats": base,
        "kpi_total": round(total),
        "kpi_count": base.count(),
        "kpi_actifs": nb_actifs,
        "types": Contrat.TypeContrat.choices,
        "statuts": Contrat.Statut.choices,
        "page_title": _("Contrats"),
    })


@login_required
@require_POST
def contrat_create(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    intitule = (request.POST.get("intitule") or "").strip()
    if exploitation and intitule:
        Contrat.objects.create(
            exploitation=exploitation,
            intitule=intitule,
            type_contrat=request.POST.get("type_contrat") or Contrat.TypeContrat.AUTRE,
            contractant=(request.POST.get("contractant") or "").strip(),
            date_debut=_to_date(request.POST.get("date_debut")),
            date_fin=_to_date(request.POST.get("date_fin")),
            montant=_to_float(request.POST.get("montant")),
            statut=request.POST.get("statut") or Contrat.Statut.BROUILLON,
            notes=(request.POST.get("notes") or "").strip(),
        )
    return redirect("contrat:contrats")


@login_required
@require_POST
def contrat_delete(request, pk):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    contrat = get_object_or_404(Contrat, pk=pk, exploitation=exploitation)
    contrat.delete()
    return redirect("contrat:contrats")


# ── Baux ────────────────────────────────────────────────────────────

@login_required
def baux(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    base = Bail.objects.filter(exploitation=exploitation) if exploitation else Bail.objects.none()

    surface = base.aggregate(s=Sum("surface_ha"))["s"] or 0
    loyer = base.aggregate(s=Sum("loyer_annuel"))["s"] or 0
    nb_actifs = base.filter(statut=Bail.Statut.ACTIF).count()

    return render(request, "contrat/baux.html", {
        "baux": base,
        "kpi_count": base.count(),
        "kpi_actifs": nb_actifs,
        "kpi_surface": round(surface, 2),
        "kpi_loyer": round(loyer),
        "statuts": Bail.Statut.choices,
        "page_title": _("Baux"),
    })


@login_required
@require_POST
def bail_create(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    designation = (request.POST.get("designation") or "").strip()
    if exploitation and designation:
        Bail.objects.create(
            exploitation=exploitation,
            designation=designation,
            bailleur=(request.POST.get("bailleur") or "").strip(),
            preneur=(request.POST.get("preneur") or "").strip(),
            surface_ha=_to_float(request.POST.get("surface_ha")),
            loyer_annuel=_to_float(request.POST.get("loyer_annuel")),
            date_debut=_to_date(request.POST.get("date_debut")),
            date_fin=_to_date(request.POST.get("date_fin")),
            statut=request.POST.get("statut") or Bail.Statut.BROUILLON,
            notes=(request.POST.get("notes") or "").strip(),
        )
    return redirect("contrat:baux")


@login_required
@require_POST
def bail_delete(request, pk):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    bail = get_object_or_404(Bail, pk=pk, exploitation=exploitation)
    bail.delete()
    return redirect("contrat:baux")


# ── Actes notariés ──────────────────────────────────────────────────

@login_required
def actes_notaries(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    base = ActeNotarie.objects.filter(exploitation=exploitation) if exploitation else ActeNotarie.objects.none()

    total = base.aggregate(s=Sum("montant"))["s"] or 0

    return render(request, "contrat/actes.html", {
        "actes": base,
        "kpi_count": base.count(),
        "kpi_total": round(total),
        "types": ActeNotarie.TypeActe.choices,
        "page_title": _("Patrimoine"),
    })


@login_required
@require_POST
def acte_create(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    objet = (request.POST.get("objet") or "").strip()
    if exploitation and objet:
        ActeNotarie.objects.create(
            exploitation=exploitation,
            objet=objet,
            type_acte=request.POST.get("type_acte") or ActeNotarie.TypeActe.AUTRE,
            notaire=(request.POST.get("notaire") or "").strip(),
            parties=(request.POST.get("parties") or "").strip(),
            reference=(request.POST.get("reference") or "").strip(),
            date_signature=_to_date(request.POST.get("date_signature")),
            montant=_to_float(request.POST.get("montant")),
            notes=(request.POST.get("notes") or "").strip(),
        )
    return redirect("contrat:actes")


@login_required
@require_POST
def acte_delete(request, pk):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    acte = get_object_or_404(ActeNotarie, pk=pk, exploitation=exploitation)
    acte.delete()
    return redirect("contrat:actes")


# ── Assurances ──────────────────────────────────────────────────────

@login_required
def assurances(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    base = Assurance.objects.filter(exploitation=exploitation) if exploitation else Assurance.objects.none()

    prime = base.aggregate(s=Sum("prime_annuelle"))["s"] or 0
    capital = base.aggregate(s=Sum("capital_assure"))["s"] or 0
    nb_actives = base.filter(statut=Assurance.Statut.ACTIVE).count()

    return render(request, "contrat/assurances.html", {
        "assurances": base,
        "kpi_count": base.count(),
        "kpi_actives": nb_actives,
        "kpi_prime": round(prime),
        "kpi_capital": round(capital),
        "types": Assurance.TypeAssurance.choices,
        "statuts": Assurance.Statut.choices,
        "page_title": _("Assurances"),
    })


@login_required
@require_POST
def assurance_create(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    intitule = (request.POST.get("intitule") or "").strip()
    if exploitation and intitule:
        Assurance.objects.create(
            exploitation=exploitation,
            intitule=intitule,
            type_assurance=request.POST.get("type_assurance") or Assurance.TypeAssurance.MULTIRISQUE,
            assureur=(request.POST.get("assureur") or "").strip(),
            numero_police=(request.POST.get("numero_police") or "").strip(),
            prime_annuelle=_to_float(request.POST.get("prime_annuelle")),
            capital_assure=_to_float(request.POST.get("capital_assure")),
            date_debut=_to_date(request.POST.get("date_debut")),
            date_fin=_to_date(request.POST.get("date_fin")),
            statut=request.POST.get("statut") or Assurance.Statut.BROUILLON,
            notes=(request.POST.get("notes") or "").strip(),
        )
    return redirect("contrat:assurances")


@login_required
@require_POST
def assurance_delete(request, pk):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    assurance = get_object_or_404(Assurance, pk=pk, exploitation=exploitation)
    assurance.delete()
    return redirect("contrat:assurances")
