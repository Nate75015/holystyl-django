"""Vues web planning : grille jour/semaine/mois d'équipe + bon d'intervention."""

import calendar as _calendar
import json
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from equipe.models import TeamMember
from exploitations.models import Exploitation

from .models import InterventionReport, PlanningTask


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


@login_required
def planning(request):
    exploitation = _exploitation(request)
    team_members = TeamMember.objects.filter(exploitation=exploitation) if exploitation else TeamMember.objects.none()

    today = timezone.localdate()

    # Vue (jour / semaine / mois) et date de référence (?vue=&date=YYYY-MM-DD).
    vue = request.GET.get("vue", "semaine")
    if vue not in ("jour", "semaine", "mois"):
        vue = "semaine"
    raw = request.GET.get("date")
    try:
        base = date.fromisoformat(raw) if raw else today
    except ValueError:
        base = today

    ctx = {
        "team_members": team_members,
        "today": today,
        "vue": vue,
        "anchor": base,
        "page_title": _("Planning"),
    }

    if vue == "jour":
        ctx.update(
            days=[base],
            ncols=1,
            label=base,
            prev_date=base - timedelta(days=1),
            next_date=base + timedelta(days=1),
            is_today_range=(base == today),
        )
    elif vue == "semaine":
        monday = base - timedelta(days=base.weekday())
        ctx.update(
            days=[monday + timedelta(days=i) for i in range(7)],
            ncols=7,
            week_start=monday,
            week_end=monday + timedelta(days=6),
            prev_date=monday - timedelta(days=7),
            next_date=monday + timedelta(days=7),
            is_today_range=(monday == today - timedelta(days=today.weekday())),
        )
    else:  # mois
        first = base.replace(day=1)
        ctx.update(
            month_weeks=_calendar.Calendar(firstweekday=0).monthdatescalendar(first.year, first.month),
            month=first,
            current_month=first.month,
            prev_date=(first - timedelta(days=1)).replace(day=1),
            next_date=(first + timedelta(days=31)).replace(day=1),
            is_today_range=(first.year == today.year and first.month == today.month),
        )

    return render(request, "planning/planning.html", ctx)


@login_required
def bon_intervention(request, task_id):
    """Bon d'intervention lié à une tâche planning (création/édition + signature)."""
    exploitation = _exploitation(request)
    task = get_object_or_404(PlanningTask, pk=task_id, exploitation=exploitation)
    report, _created = InterventionReport.objects.get_or_create(
        planning_task=task,
        exploitation=exploitation,
        defaults={
            "titre": task.titre,
            "intervention_type": task.type,
            "client_nom": task.client_nom,
            "technicien_nom": task.technicien_nom,
            "date_intervention": timezone.localdate(),
        },
    )

    if request.method == "POST":
        report.description_travaux = request.POST.get("description_travaux", "")
        report.observations = request.POST.get("observations", "")
        report.recommandations = request.POST.get("recommandations", "")
        report.signature_client_url = request.POST.get("signature_client_url", "")
        report.signature_client_nom = request.POST.get("signature_client_nom", "")
        report.signature_tech_url = request.POST.get("signature_tech_url", "")
        produits = request.POST.get("produits_utilises")
        if produits:
            try:
                report.produits_utilises = json.loads(produits)
            except json.JSONDecodeError:
                pass
        if request.POST.get("action") == "validate":
            report.statut = InterventionReport.Statut.VALIDE
        else:
            report.statut = InterventionReport.Statut.COMPLETE
        report.save()
        messages.success(request, _("Bon d'intervention enregistré."))
        return redirect("planning:planning")

    return render(
        request,
        "planning/bon_intervention.html",
        {"task": task, "report": report, "page_title": _("Bon d'intervention")},
    )
