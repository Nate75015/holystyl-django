"""Vues web finances : charges, revenus, bilan économique, facturation."""

from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from contrat import fermages as calcul_fermages
from contrat.models import Bail, IndiceFermage
from exploitations.models import Exploitation
from parcelles.models import Parcelle

from .models import Charge, Facture, Revenu
from .services import compute_bilan


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


def _to_float(value):
    """Montant saisi (« 12,50 » ou « 12.50 ») → float, ou None si vide/invalide."""
    try:
        return float(str(value).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


@login_required
def charges(request):
    exploitation = _exploitation(request)
    charges_qs = (
        Charge.objects.filter(exploitation=exploitation).select_related("parcelle")
        if exploitation else Charge.objects.none()
    )
    revenus_qs = (
        Revenu.objects.filter(exploitation=exploitation).select_related("parcelle")
        if exploitation else Revenu.objects.none()
    )
    return render(request, "finances/charges.html", {
        "charges": charges_qs,
        "revenus": revenus_qs,
        "bilan": compute_bilan(exploitation),
        "categories": Charge.Categorie.choices,
        "revenu_categories": Revenu.Categorie.choices,
        "parcelles": Parcelle.objects.filter(exploitation=exploitation) if exploitation else Parcelle.objects.none(),
        "today": timezone.localdate().isoformat(),
        "page_title": _("Charges & Coûts"),
    })


@login_required
@require_POST
def charge_create(request):
    """Enregistre une charge depuis la modale « Enregistrer une charge »."""
    exploitation = _exploitation(request)
    montant = _to_float(request.POST.get("montant"))
    if exploitation and montant is not None:
        d = parse_date(request.POST.get("date") or "")
        dt = timezone.make_aware(datetime.combine(d, datetime.min.time())) if d else timezone.now()
        categorie = request.POST.get("categorie")
        if categorie not in Charge.Categorie.values:
            categorie = Charge.Categorie.AUTRE
        Charge.objects.create(
            exploitation=exploitation,
            parcelle=Parcelle.objects.filter(pk=request.POST.get("parcelle") or None, exploitation=exploitation).first(),
            date=dt,
            categorie=categorie,
            montant=montant,
            description=(request.POST.get("description") or "").strip()[:500],
            fournisseur=(request.POST.get("fournisseur") or "").strip()[:255],
        )
    return redirect("finances:charges")


@login_required
@require_POST
def revenu_create(request):
    """Enregistre un revenu depuis la modale « Enregistrer un revenu »."""
    exploitation = _exploitation(request)
    montant = _to_float(request.POST.get("montant"))
    if exploitation and montant is not None:
        d = parse_date(request.POST.get("date") or "")
        dt = timezone.make_aware(datetime.combine(d, datetime.min.time())) if d else timezone.now()
        categorie = request.POST.get("categorie")
        if categorie not in Revenu.Categorie.values:
            categorie = Revenu.Categorie.AUTRE
        Revenu.objects.create(
            exploitation=exploitation,
            parcelle=Parcelle.objects.filter(pk=request.POST.get("parcelle") or None, exploitation=exploitation).first(),
            date=dt,
            categorie=categorie,
            montant=montant,
            description=(request.POST.get("description") or "").strip()[:500],
            acheteur=(request.POST.get("acheteur") or "").strip()[:255],
            quantite_kg=_to_float(request.POST.get("quantite_kg")),
            prix_unitaire=_to_float(request.POST.get("prix_unitaire")),
        )
    return redirect("finances:charges")


@login_required
def bilan_economique(request):
    from django.db.models import Sum
    from django.db.models.functions import TruncMonth

    exploitation = _exploitation(request)
    bilan = compute_bilan(exploitation)
    revenus = Revenu.objects.filter(exploitation=exploitation) if exploitation else Revenu.objects.none()

    chart = None
    if exploitation is not None:
        def monthly(model):
            rows = (
                model.objects.filter(exploitation=exploitation)
                .annotate(m=TruncMonth("date")).values("m")
                .annotate(total=Sum("montant")).order_by("m")
            )
            return {r["m"].strftime("%m/%Y"): round(r["total"] or 0, 0) for r in rows if r["m"]}

        rev, chg = monthly(Revenu), monthly(Charge)
        labels = sorted(set(rev) | set(chg))
        if labels:
            chart = {
                "labels": labels,
                "type": "bar",
                "datasets": [
                    {"label": str(_("Revenus")), "data": [rev.get(m, 0) for m in labels], "color": "#22c55e"},
                    {"label": str(_("Charges")), "data": [chg.get(m, 0) for m in labels], "color": "#ef4444"},
                ],
            }

    return render(
        request,
        "finances/bilan_economique.html",
        {"bilan": bilan, "revenus": revenus, "chart": chart, "page_title": _("Bilan économique")},
    )


@login_required
def facturation(request):
    exploitation = _exploitation(request)
    factures = Facture.objects.filter(exploitation=exploitation) if exploitation else Facture.objects.none()
    return render(request, "finances/facturation.html", {"factures": factures, "page_title": _("Facturation")})


# ── Fermage : révision des loyers par l'indice national ──────────────────

@login_required
def fermage(request):
    """Calcul du fermage dû : loyer de base révisé par les indices nationaux."""
    exploitation = _exploitation(request)
    baux = (
        Bail.objects.filter(exploitation=exploitation).exclude(statut=Bail.Statut.RESILIE)
        if exploitation else Bail.objects.none()
    )
    indices_qs = IndiceFermage.objects.all()
    indices = {i.annee: i.variation_pct for i in indices_qs}

    annees_connues = sorted(indices) or [timezone.now().year]
    try:
        annee = int(request.GET.get("annee") or annees_connues[-1])
    except (TypeError, ValueError):
        annee = annees_connues[-1]

    lignes = [calcul_fermages.ligne_bail(b, indices, annee) for b in baux]
    total = sum(l["total_annuel"] or 0 for l in lignes)
    return render(request, "finances/fermage.html", {
        "lignes": lignes,
        "indices": indices_qs,
        "annee": annee,
        "annees": annees_connues,
        "total_annuel": round(total, 2),
        "page_title": _("Fermage"),
    })


@login_required
@require_POST
def indice_fermage_add(request):
    """Ajoute (ou met à jour) l'indice d'une année — référentiel commun."""
    try:
        annee = int(request.POST.get("annee") or 0)
    except (TypeError, ValueError):
        annee = 0
    variation = _to_float(request.POST.get("variation_pct"))
    if annee and variation is not None:
        IndiceFermage.objects.update_or_create(
            annee=annee,
            defaults={
                "variation_pct": variation,
                "reference": (request.POST.get("reference") or "").strip()[:255],
            },
        )
    else:
        messages.error(request, _("Indice incomplet : année et variation sont requises."))
    return redirect("finances:fermage")


@login_required
@require_POST
def indice_fermage_delete(request, pk):
    IndiceFermage.objects.filter(pk=pk).delete()
    return redirect("finances:fermage")


@login_required
@require_POST
def bail_fermage_update(request, pk):
    """Paramètres de révision d'un bail (loyer de base, année, encadrement)."""
    exploitation = _exploitation(request)
    bail = get_object_or_404(Bail, pk=pk, exploitation=exploitation)
    bail.loyer_base_ha = _to_float(request.POST.get("loyer_base_ha"))
    bail.loyer_mini_ha = _to_float(request.POST.get("loyer_mini_ha"))
    bail.loyer_maxi_ha = _to_float(request.POST.get("loyer_maxi_ha"))
    try:
        bail.annee_reference = int(request.POST.get("annee_reference") or 0) or None
    except (TypeError, ValueError):
        bail.annee_reference = None
    bail.save(update_fields=["loyer_base_ha", "annee_reference", "loyer_mini_ha", "loyer_maxi_ha"])
    return redirect(f"{reverse('finances:fermage')}?annee={request.POST.get('annee') or ''}")
