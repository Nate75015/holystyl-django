"""Vues web Environnement : pages-cadre + Taxonomie EU."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from exploitations.models import Exploitation

from .models import ActiviteTaxonomie


def _to_float(value, default=None):
    try:
        return float(str(value).replace(",", ".").replace("€", "").replace(" ", "").strip())
    except (TypeError, ValueError):
        return default


def _exploitation(request, create=False):
    exp = Exploitation.objects.filter(owner=request.user).first()
    if exp is None and create:
        exp = Exploitation.objects.create(
            owner=request.user,
            name=(getattr(request.user, "full_name", "") or "Mon exploitation")[:255],
        )
    return exp


def _page(request, title, icon, desc):
    return render(request, "environnement/placeholder.html", {
        "title": title, "icon": icon, "desc": desc, "page_title": title,
    })


@login_required
def biodiversite(request):
    return _page(request, _("Biodiversité"), "eco", _(
        "Suivez la biodiversité de vos parcelles : auxiliaires, pollinisateurs, "
        "couverts végétaux et infrastructures agro-écologiques (IAE)."))


@login_required
def bilan_eau(request):
    return _page(request, _("Bilan eau"), "water_drop", _(
        "Bilan hydrique de l'exploitation : volumes prélevés, irrigation, "
        "pluie efficace et efficience de l'eau (m³/ha)."))


@login_required
def bilan_azote(request):
    return _page(request, _("Bilan azoté"), "science", _(
        "Bilan azoté (méthode du bilan) : entrées, exports par les cultures, "
        "reliquats et pression sur la directive Nitrates."))


@login_required
def empreinte_carbone(request):
    return _page(request, _("Empreinte carbone"), "cloud", _(
        "Émissions de gaz à effet de serre de l'exploitation et stockage carbone "
        "des sols (diagnostic type GES / label bas-carbone)."))


@login_required
def rapport_environnemental(request):
    return _page(request, _("Rapport environnemental"), "assessment", _(
        "Synthèse environnementale de l'exploitation, exportable, regroupant les "
        "indicateurs (eau, azote, carbone, biodiversité)."))


@login_required
def sante_vegetale(request):
    return _page(request, _("Santé végétale"), "local_florist", _(
        "Suivi sanitaire des cultures : maladies, ravageurs, observations et "
        "indicateurs de fréquence de traitement (IFT)."))


# ── Taxonomie EU ────────────────────────────────────────────────────

@login_required
def taxonomie(request):
    exploitation = _exploitation(request)
    base = ActiviteTaxonomie.objects.filter(exploitation=exploitation) if exploitation else ActiviteTaxonomie.objects.none()

    annees = sorted(set(base.values_list("campagne", flat=True)), reverse=True)
    current = timezone.now().year
    if current not in annees:
        annees = [current] + annees
    try:
        campagne = int(request.GET.get("campagne") or annees[0])
    except (ValueError, IndexError):
        campagne = current

    fiches = list(base.filter(campagne=campagne))

    def _pct(attr):
        total = sum((getattr(f, attr) or 0) for f in fiches)
        aligned = sum((getattr(f, attr) or 0) for f in fiches if f.aligne)
        return round(aligned / total * 100) if total else 0

    return render(request, "environnement/taxonomie.html", {
        "fiches": fiches,
        "annees": annees,
        "campagne": campagne,
        "pct_ca": _pct("chiffre_affaires"),
        "pct_capex": _pct("capex"),
        "pct_opex": _pct("opex"),
        "nb_fiches": len(fiches),
        "nb_alignes": sum(1 for f in fiches if f.aligne),
        "objectifs": ActiviteTaxonomie.Objectif.choices,
        "page_title": _("Taxonomie EU"),
    })


@login_required
@require_POST
def taxonomie_create(request):
    exploitation = _exploitation(request, create=True)
    try:
        campagne = int(request.POST.get("campagne") or timezone.now().year)
    except (ValueError, TypeError):
        campagne = timezone.now().year
    dnsh = {value: (request.POST.get(f"dnsh_{value}") == "on") for value, _label in ActiviteTaxonomie.Objectif.choices}
    ActiviteTaxonomie.objects.create(
        exploitation=exploitation,
        campagne=campagne,
        libelle=(request.POST.get("libelle") or "").strip()[:255] or "Activité",
        code_nace=(request.POST.get("code_nace") or "").strip()[:20],
        objectif=request.POST.get("objectif") or ActiviteTaxonomie.Objectif.ATTENUATION,
        eligible=request.POST.get("eligible") == "on",
        contribution=request.POST.get("contribution") == "on",
        garanties=request.POST.get("garanties") == "on",
        dnsh=dnsh,
        chiffre_affaires=_to_float(request.POST.get("chiffre_affaires")),
        capex=_to_float(request.POST.get("capex")),
        opex=_to_float(request.POST.get("opex")),
        justification=(request.POST.get("justification") or "").strip(),
    )
    return redirect(f"{reverse('environnement:taxonomie')}?campagne={campagne}")


@login_required
@require_POST
def taxonomie_delete(request, pk):
    exploitation = _exploitation(request)
    obj = get_object_or_404(ActiviteTaxonomie, pk=pk, exploitation=exploitation)
    campagne = obj.campagne
    obj.delete()
    return redirect(f"{reverse('environnement:taxonomie')}?campagne={campagne}")
