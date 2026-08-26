"""Bilan économique / ROI et préparation des dossiers de subvention.

Reproduit `bilan.roi` (gains nets = revenus − charges, marges) et l'assemblage
des données de subvention (parité `reports.exportSubvention`).
"""

from dataclasses import asdict, dataclass

from django.db.models import Sum
from django.utils import timezone

from irrigation.models import DtiScore, EnergyLog, WaterMeter

from .models import Charge, Facture, Revenu


def prochain_numero(exploitation, modele=Facture, lettre="F") -> str:
    """Numéro suivant, séquentiel par année et par série (F-2026-004, D-2026-002).

    Le numéro ne doit contenir ni espace ni caractère exotique : la règle
    française BR-FR-01 rejette la facture sinon. Ce calcul vit ici et non dans
    une vue : la vente directe émet aussi des factures, et deux implantations
    finiraient par diverger — donc par produire deux fois le même numéro.
    """
    annee = timezone.localdate().year
    prefixe = f"{lettre}-{annee}-"
    if not exploitation:
        return f"{prefixe}001"
    existants = (
        modele.objects.filter(exploitation=exploitation, numero__startswith=prefixe)
        .values_list("numero", flat=True)
    )
    rangs = [int(n.rsplit("-", 1)[-1]) for n in existants if n.rsplit("-", 1)[-1].isdigit()]
    return f"{prefixe}{(max(rangs) + 1) if rangs else 1:03d}"


@dataclass
class Bilan:
    total_revenus: float = 0.0
    total_charges: float = 0.0
    resultat_net: float = 0.0
    surface_ha: float = 0.0
    marge_par_ha: float | None = None
    eau_m3: float = 0.0
    energie_kwh: float = 0.0


def compute_bilan(exploitation, year: int | None = None) -> Bilan:
    if exploitation is None:
        return Bilan()
    charges = Charge.objects.filter(exploitation=exploitation)
    revenus = Revenu.objects.filter(exploitation=exploitation)
    if year:
        charges = charges.filter(date__year=year)
        revenus = revenus.filter(date__year=year)

    total_rev = revenus.aggregate(s=Sum("montant"))["s"] or 0.0
    total_chg = charges.aggregate(s=Sum("montant"))["s"] or 0.0
    surface = exploitation.parcelles.aggregate(s=Sum("area"))["s"] or exploitation.total_area or 0.0
    eau = WaterMeter.objects.filter(exploitation=exploitation).aggregate(s=Sum("volume_m3"))["s"] or 0.0
    energie = EnergyLog.objects.filter(exploitation=exploitation).aggregate(s=Sum("energy_kwh"))["s"] or 0.0

    resultat = total_rev - total_chg
    return Bilan(
        total_revenus=round(total_rev, 2),
        total_charges=round(total_chg, 2),
        resultat_net=round(resultat, 2),
        surface_ha=round(surface, 2),
        marge_par_ha=round(resultat / surface, 2) if surface else None,
        eau_m3=round(eau, 2),
        energie_kwh=round(energie, 2),
    )


def subvention_context(exploitation, export_type: str, year: int | None = None) -> dict:
    """Assemble les données d'un dossier de subvention (PDF certifié)."""
    bilan = compute_bilan(exploitation, year)
    latest_dti = DtiScore.objects.filter(exploitation=exploitation).first()
    return {
        "exploitation": exploitation,
        "export_type": export_type,
        "year": year,
        "bilan": asdict(bilan),
        "dti": latest_dti,
        "parcelles": exploitation.parcelles.all(),
    }
