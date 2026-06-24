"""Vues web analyses de sol : liste + KPIs, import d'une analyse (document)."""

from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from exploitations.models import Exploitation
from parcelles.models import Parcelle

from .models import AnalyseSol
from .services import extract_soil_analysis


def _to_float(value, default=None):
    try:
        return float(str(value).replace(",", ".").strip())
    except (TypeError, ValueError):
        return default


@login_required
def analyses_sol(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    items = (
        AnalyseSol.objects.filter(exploitation=exploitation).select_related("parcelle")
        if exploitation
        else AnalyseSol.objects.none()
    )
    agg = items.aggregate(ph=Avg("ph"), mo=Avg("matiere_organique"))
    return render(request, "analyse_sol/analyses_sol.html", {
        "analyses": items,
        "kpi_count": items.count(),
        "kpi_parcelles": items.values("parcelle").distinct().count(),
        "kpi_ph": round(agg["ph"], 1) if agg["ph"] is not None else None,
        "kpi_mo": round(agg["mo"], 1) if agg["mo"] is not None else None,
        "parcelles": Parcelle.objects.filter(exploitation=exploitation) if exploitation else Parcelle.objects.none(),
        "page_title": _("Analyses de sol"),
    })


@login_required
@require_POST
def analyse_sol_create(request):
    """Import d'une analyse : parcelle + date + document, valeurs extraites par OCR/IA."""
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    parcelle = Parcelle.objects.filter(pk=request.POST.get("parcelle"), exploitation=exploitation).first()
    if not (exploitation and parcelle):
        return redirect("analyse_sol:analyses_sol")

    d = parse_date(request.POST.get("date") or "")
    dt = timezone.make_aware(datetime.combine(d, datetime.min.time())) if d else timezone.now()

    document = request.FILES.get("document")
    doc_bytes = document.read() if document else b""
    doc_name = document.name if document else ""
    if document:
        document.seek(0)  # rembobine pour que le fichier soit sauvegardé entièrement

    analyse = AnalyseSol.objects.create(exploitation=exploitation, parcelle=parcelle, date=dt, document=document)

    # OCR/IA : extraction automatique des valeurs depuis le document
    extracted = extract_soil_analysis(doc_bytes, doc_name) if doc_bytes else None
    if extracted:
        analyse.laboratoire = (extracted.get("laboratoire") or "")[:255]
        analyse.ph = _to_float(extracted.get("ph"))
        analyse.ec = _to_float(extracted.get("ec"))
        analyse.azote_total = _to_float(extracted.get("azote_total"))
        analyse.phosphore_assimilable = _to_float(extracted.get("phosphore_assimilable"))
        analyse.potassium_echangeable = _to_float(extracted.get("potassium_echangeable"))
        analyse.matiere_organique = _to_float(extracted.get("matiere_organique"))
        analyse.calcaire_total = _to_float(extracted.get("calcaire_total"))
        analyse.save()
    return redirect("analyse_sol:analyses_sol")
