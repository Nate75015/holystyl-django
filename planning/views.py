"""Vues web planning : calendrier des interventions + bon d'intervention."""

import json

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
    tasks = PlanningTask.objects.filter(exploitation=exploitation) if exploitation else PlanningTask.objects.none()
    technicians = TeamMember.objects.filter(exploitation=exploitation) if exploitation else TeamMember.objects.none()
    return render(
        request,
        "planning/planning.html",
        {
            "tasks": tasks,
            "backlog": tasks.filter(is_backlog=True),
            "technicians": technicians,
            "views": [("jour", _("Jour")), ("semaine", _("Semaine")), ("mois", _("Mois"))],
            "page_title": _("Planning"),
        },
    )


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
