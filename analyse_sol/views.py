"""Vues web analyses de sol : liste + KPIs, import d'une analyse (document)."""

from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from exploitations.models import Exploitation
from parcelles.models import Parcelle

from .forms import FIELD_GROUPS, AnalyseSolForm
from .models import AnalyseSol, DemandeAnalyse, Laboratoire
from .services import DATE_FIELDS, TEXT_FIELDS, extract_soil_analysis


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
    demandes = (
        DemandeAnalyse.objects.filter(exploitation=exploitation).select_related("parcelle", "laboratoire")
        if exploitation
        else DemandeAnalyse.objects.none()
    )
    return render(request, "analyse_sol/analyses_sol.html", {
        "analyses": items,
        "demandes": demandes,
        "laboratoires": Laboratoire.objects.filter(actif=True),
        "types_demande": DemandeAnalyse.Type.choices,
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
        for field, value in extracted.items():
            if value is None or value == "":
                continue
            if field in DATE_FIELDS:
                parsed = parse_date(str(value))
                if parsed:
                    setattr(analyse, field, parsed)
            elif field in TEXT_FIELDS:
                setattr(analyse, field, str(value)[:255])
            else:  # champ numérique
                setattr(analyse, field, _to_float(value))
        analyse.save()
    return redirect("analyse_sol:analyses_sol")


# Icône Material et ancre par section (dans l'ordre de FIELD_GROUPS).
_SECTION_ICONS = {
    "Général": "tune",
    "Identification (labo)": "badge",
    "pH & calcaire": "science",
    "MO, carbone & azote": "eco",
    "Éléments majeurs": "spa",
    "Oligo-éléments": "biotech",
    "CEC & équilibre cationique": "balance",
    "Granulométrie / texture": "grain",
    "Propriétés physiques & réserve en eau": "water_drop",
    "Éléments traces métalliques": "warning_amber",
    "Contaminants organiques (annexe)": "coronavirus",
    "Notes": "edit_note",
}


@login_required
def analyse_sol_edit(request, pk):
    """Édition de tous les champs d'une analyse (page dédiée, groupée par section)."""
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    analyse = get_object_or_404(AnalyseSol, pk=pk, exploitation=exploitation)
    form = AnalyseSolForm(request.POST or None, instance=analyse, exploitation=exploitation)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Analyse mise à jour."))
        return redirect("analyse_sol:analyses_sol")

    # Métadonnées d'affichage : icône, ancre, et nb de champs renseignés par section.
    groups, filled_total, fields_total = [], 0, 0
    for index, (title, names) in enumerate(FIELD_GROUPS):
        filled = sum(1 for n in names if getattr(analyse, n) not in (None, ""))
        filled_total += filled
        fields_total += len(names)
        groups.append({
            "title": title,
            "icon": _SECTION_ICONS.get(title, "science"),
            "anchor": f"section-{index}",
            "fields": [form[n] for n in names],
            "filled": filled,
            "count": len(names),
        })
    return render(request, "analyse_sol/edit.html", {
        "form": form,
        "analyse": analyse,
        "groups": groups,
        "filled_total": filled_total,
        "fields_total": fields_total,
        "filled_pct": round(100 * filled_total / fields_total) if fields_total else 0,
        "page_title": _("Modifier l'analyse"),
    })


def _pct_number(value):
    """Extrait la 1re valeur numérique d'un texte (« >100 » → 100.0, « 95,4 » → 95.4)."""
    import re

    match = re.search(r"[0-9]+(?:[.,][0-9]+)?", str(value or ""))
    return float(match.group().replace(",", ".")) if match else 0.0


@login_required
def analyse_sol_detail(request, pk):
    """Consultation en lecture seule de tous les champs d'une analyse."""
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    analyse = get_object_or_404(
        AnalyseSol.objects.select_related("parcelle"), pk=pk, exploitation=exploitation
    )
    groups, filled_total, fields_total = [], 0, 0
    for index, (title, names) in enumerate(FIELD_GROUPS):
        rows, filled = [], 0
        for name in names:
            raw = getattr(analyse, name)
            if name == "parcelle":
                value = analyse.parcelle.name if analyse.parcelle else ""
            elif name == "date":
                value = analyse.date.strftime("%d/%m/%Y %H:%M") if analyse.date else ""
            elif name in DATE_FIELDS:
                value = raw.strftime("%d/%m/%Y") if raw else ""
            else:
                value = "" if raw in (None, "") else raw
            has = value not in ("", None)
            filled += 1 if has else 0
            row = {"label": AnalyseSol._meta.get_field(name).verbose_name, "value": value,
                   "name": name, "has": has}
            if name == "taux_saturation" and has:
                row["sat_width"] = min(100, max(0, _pct_number(value)))
                row["sat_over"] = _pct_number(value) > 100 or ">" in str(value)
            rows.append(row)
        filled_total += filled
        fields_total += len(names)
        groups.append({
            "title": title, "icon": _SECTION_ICONS.get(title, "science"),
            "anchor": f"section-{index}", "rows": rows, "filled": filled, "count": len(names),
        })
    return render(request, "analyse_sol/detail.html", {
        "analyse": analyse,
        "groups": groups,
        "filled_total": filled_total,
        "fields_total": fields_total,
        "filled_pct": round(100 * filled_total / fields_total) if fields_total else 0,
        "page_title": _("Analyse de sol"),
    })


@login_required
@require_POST
def analyse_sol_delete(request, pk):
    """Supprime une analyse (et son document)."""
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    analyse = get_object_or_404(AnalyseSol, pk=pk, exploitation=exploitation)
    analyse.delete()
    messages.success(request, _("Analyse supprimée."))
    return redirect("analyse_sol:analyses_sol")


@login_required
@require_POST
def demande_create(request):
    """Enregistre une demande d'analyse adressée à un laboratoire partenaire."""
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    parcelle = Parcelle.objects.filter(pk=request.POST.get("parcelle"), exploitation=exploitation).first()
    laboratoire = Laboratoire.objects.filter(pk=request.POST.get("laboratoire"), actif=True).first()
    if exploitation and parcelle and laboratoire:
        type_analyse = request.POST.get("type_analyse") or DemandeAnalyse.Type.COMPLETE
        if type_analyse not in DemandeAnalyse.Type.values:
            type_analyse = DemandeAnalyse.Type.COMPLETE
        DemandeAnalyse.objects.create(
            exploitation=exploitation,
            parcelle=parcelle,
            laboratoire=laboratoire,
            user=request.user,
            type_analyse=type_analyse,
            message=(request.POST.get("message") or "").strip(),
        )
    return redirect("analyse_sol:analyses_sol")
