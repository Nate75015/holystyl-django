"""Vues web Environnement : pages-cadre + Taxonomie EU."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

import csv
from collections import defaultdict

from django.http import HttpResponse

from exploitations.models import Exploitation
from irrigation.models import IrrigationSession
from parcelles.models import Parcelle

from .models import ActiviteTaxonomie

_DEFAULT_QUOTA_M3 = 45000.0
_PRIX_EAU_M3 = 0.08


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


def _bilan_eau_data(request):
    exploitation = _exploitation(request)
    sessions = (
        list(IrrigationSession.objects.filter(exploitation=exploitation).select_related("parcelle"))
        if exploitation else []
    )
    total_m3 = sum(s.volume_delivered_m3 or 0 for s in sessions)
    quota = exploitation.water_quota_m3 if exploitation and exploitation.water_quota_m3 else _DEFAULT_QUOTA_M3
    prix_m3 = exploitation.prix_eau_m3 if exploitation and exploitation.prix_eau_m3 is not None else _PRIX_EAU_M3

    # Consommation mensuelle
    monthly = defaultdict(float)
    for s in sessions:
        if s.start_time and s.volume_delivered_m3:
            monthly[s.start_time.strftime("%Y-%m")] += s.volume_delivered_m3
    months = sorted(monthly)

    # Consommation quotidienne, un graphique par parcelle (TOUTES les parcelles)
    parcelles = list(Parcelle.objects.filter(exploitation=exploitation)) if exploitation else []
    daily_by_parcelle = defaultdict(lambda: defaultdict(float))
    for s in sessions:
        if s.parcelle_id and s.start_time and s.volume_delivered_m3:
            daily_by_parcelle[s.parcelle_id][s.start_time.strftime("%Y-%m-%d")] += s.volume_delivered_m3

    parcelle_charts = []
    for p in parcelles:
        days = daily_by_parcelle.get(p.pk, {})
        ordered = sorted(days)
        parcelle_charts.append({
            "nom": p.name,
            "total": round(sum(days.values()), 1),
            "labels": [f"{d[8:10]}/{d[5:7]}" for d in ordered],
            "data": [round(days[d], 1) for d in ordered],
        })
    parcelle_charts.sort(key=lambda c: c["total"], reverse=True)

    return {
        "exploitation": exploitation,
        "sessions": sessions,
        "total_m3": round(total_m3, 1),
        "nb_sessions": len(sessions),
        "quota": quota,
        "quota_display": f"{int(quota):,}".replace(",", " "),
        "pct_quota": round(total_m3 / quota * 100, 1) if quota else 0,
        "cout": round(total_m3 * prix_m3),
        "prix_m3": prix_m3,
        "monthly_chart": {
            "labels": [f"{m[5:7]}/{m[:4]}" for m in months],
            "data": [round(monthly[m], 1) for m in months],
        },
        "parcelle_charts": parcelle_charts,
        "has_parcelles": bool(parcelles),
    }


@login_required
def bilan_eau(request):
    ctx = _bilan_eau_data(request)
    ctx["page_title"] = _("Bilan Eau")
    return render(request, "environnement/bilan_eau.html", ctx)


@login_required
def bilan_eau_export(request):
    data = _bilan_eau_data(request)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="bilan_eau.csv"'
    writer = csv.writer(response)
    writer.writerow(["Date", "Parcelle", "Volume (m³)", "Déclencheur", "kWh/m³"])
    for s in data["sessions"]:
        writer.writerow([
            s.start_time.strftime("%d/%m/%Y %H:%M") if s.start_time else "",
            s.parcelle.name if s.parcelle else "",
            s.volume_delivered_m3 or "",
            s.get_triggered_by_display(),
            s.kwh_per_m3 or "",
        ])
    return response


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
