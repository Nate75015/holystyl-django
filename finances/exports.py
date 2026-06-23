"""Exports PDF (WeasyPrint) et CSV — parité /api/reports/pdf et /api/reports/csv."""

import csv

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.template.loader import render_to_string

from exploitations.models import Exploitation

from .models import Charge, Revenu, SubventionExport
from .services import subvention_context


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


@login_required
def report_pdf(request):
    """Dossier de subvention en PDF certifié.

    Paramètres : type (taxonomie_verte|plan_eau_2026|pac|feader), year.
    """
    exploitation = _exploitation(request)
    export_type = request.GET.get("type", "taxonomie_verte")
    year = request.GET.get("year")
    year = int(year) if year and year.isdigit() else None

    ctx = subvention_context(exploitation, export_type, year)
    html = render_to_string("finances/subvention_pdf.html", ctx)

    try:
        from weasyprint import HTML

        pdf = HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()
    except Exception:  # pragma: no cover - dépend des libs système
        return HttpResponse("Génération PDF indisponible sur ce serveur.", status=501)

    # Trace l'export généré
    if exploitation:
        SubventionExport.objects.create(
            exploitation=exploitation, export_type=export_type,
            period=str(year or ""), status=SubventionExport.Status.READY,
        )
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="subvention_{export_type}_{year or "all"}.pdf"'
    return resp


@login_required
def report_csv(request):
    """Export CSV : type = charges | revenus."""
    exploitation = _exploitation(request)
    kind = request.GET.get("type", "charges")
    year = request.GET.get("year")

    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="{kind}_{year or "all"}.csv"'
    writer = csv.writer(resp)

    if kind == "revenus":
        qs = Revenu.objects.filter(exploitation=exploitation)
        if year and year.isdigit():
            qs = qs.filter(date__year=int(year))
        writer.writerow(["date", "categorie", "montant", "acheteur", "description"])
        for r in qs:
            writer.writerow([r.date.date(), r.categorie, r.montant, r.acheteur, r.description])
    else:
        qs = Charge.objects.filter(exploitation=exploitation)
        if year and year.isdigit():
            qs = qs.filter(date__year=int(year))
        writer.writerow(["date", "categorie", "montant", "fournisseur", "description"])
        for c in qs:
            writer.writerow([c.date.date(), c.categorie, c.montant, c.fournisseur, c.description])

    return resp
