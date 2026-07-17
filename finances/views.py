"""Vues web finances : charges, revenus, bilan économique, facturation."""

from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from agronomie.models import Saison
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
        "saison_active": Saison.objects.filter(exploitation=exploitation, active=True).first() if exploitation else None,
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
            # Rattaché à la saison active pour le bilan par saison.
            saison=Saison.objects.filter(exploitation=exploitation, active=True).first(),
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
