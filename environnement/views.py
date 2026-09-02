"""Vues web Environnement : pages-cadre + Taxonomie EU."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST



from exploitations.models import Exploitation
from parcelles.models import Parcelle

from django.db.models import Avg, Sum
from django.utils.dateparse import parse_date

from .models import ActiviteTaxonomie, Biodiversite



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


def _int(value):
    try:
        return int(float(str(value).replace(",", ".").strip()))
    except (TypeError, ValueError):
        return None


@login_required
def biodiversite(request):
    exploitation = _exploitation(request)
    fiches = (
        Biodiversite.objects.filter(exploitation=exploitation).select_related("parcelle")
        if exploitation else Biodiversite.objects.none()
    )
    agg = fiches.aggregate(score=Avg("score"), haies=Sum("haies_ml"), jachere=Sum("jachere_ha"))
    return render(request, "environnement/biodiversite.html", {
        "fiches": fiches,
        "kpi_score": round(agg["score"]) if agg["score"] is not None else None,
        "kpi_haies": round(agg["haies"]) if agg["haies"] else 0,
        "kpi_jachere": round(agg["jachere"], 1) if agg["jachere"] else 0,
        "parcelles": Parcelle.objects.filter(exploitation=exploitation) if exploitation else Parcelle.objects.none(),
        "today": timezone.localdate().isoformat(),
        "page_title": _("Biodiversité"),
    })


def _save_biodiversite(fiche, request, exploitation):
    """Applique les champs POST à une fiche (création ou édition). False si parcelle invalide."""
    parcelle = Parcelle.objects.filter(pk=request.POST.get("parcelle"), exploitation=exploitation).first()
    if not parcelle:
        return False
    score = _int(request.POST.get("score"))
    fiche.parcelle = parcelle
    fiche.date = parse_date(request.POST.get("date") or "") or timezone.localdate()
    fiche.score = max(0, min(100, score)) if score is not None else None
    fiche.especes_vegetales = _int(request.POST.get("especes_vegetales"))
    fiche.especes_animales = _int(request.POST.get("especes_animales"))
    fiche.haies_ml = _to_float(request.POST.get("haies_ml"))
    fiche.jachere_ha = _to_float(request.POST.get("jachere_ha"))
    fiche.observations = (request.POST.get("observations") or "").strip()
    fiche.save()
    return True


@login_required
@require_POST
def biodiversite_create(request):
    """Enregistre une fiche biodiversité depuis la modale « Nouvelle fiche »."""
    exploitation = _exploitation(request, create=True)
    _save_biodiversite(Biodiversite(exploitation=exploitation), request, exploitation)
    return redirect("environnement:biodiversite")


@login_required
@require_POST
def biodiversite_edit(request, pk):
    """Met à jour une fiche existante (soumise depuis la modale d'édition)."""
    exploitation = _exploitation(request)
    fiche = get_object_or_404(Biodiversite, pk=pk, exploitation=exploitation)
    _save_biodiversite(fiche, request, exploitation)
    return redirect("environnement:biodiversite")


@login_required
@require_POST
def biodiversite_delete(request, pk):
    """Supprime une fiche biodiversité."""
    exploitation = _exploitation(request)
    get_object_or_404(Biodiversite, pk=pk, exploitation=exploitation).delete()
    return redirect("environnement:biodiversite")


# ── Bilan eau : la page a rejoint le DTI ────────────────────────────
#
# Elle répondait à la même question que le diagnostic — ce que l'installation
# fait de l'eau — depuis un autre menu. Les deux adresses subsistent en
# redirection permanente : un lien partagé ou un signet doit continuer de
# mener quelque part.


@login_required
def bilan_eau(request):
    return redirect("irrigation:dti", permanent=True)


@login_required
def bilan_eau_export(request):
    return redirect("irrigation:bilan_eau_export", permanent=True)


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
