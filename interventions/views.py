"""Vues web interventions : journal des opérations culturales."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from equipe.models import Task, TeamMember
from exploitations.models import Exploitation
from parcelles.models import Parcelle

from .models import Intervention


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


# Icône Material + couleur par type d'opération (bande « Par type d'opération »).
# Les couleurs sont dans la safelist Tailwind (cf. tailwind.config.js).
TYPE_META = {
    "irrigation": ("water_drop", "blue"), "traitement": ("science", "purple"),
    "fertilisation": ("eco", "emerald"), "recolte": ("agriculture", "amber"),
    "semis": ("grass", "green"), "travail_sol": ("terrain", "orange"),
    "taille": ("content_cut", "rose"), "palissage": ("linear_scale", "slate"),
    "desherbage": ("yard", "lime"), "eclaircissage": ("filter_vintage", "teal"),
    "effeuillage": ("spa", "cyan"), "vendange": ("local_bar", "fuchsia"),
    "maintenance": ("build", "gray"), "observation": ("visibility", "sky"),
    "autre": ("category", "stone"),
}


@login_required
def interventions(request):
    exploitation = _exploitation(request)
    items = (
        Intervention.objects.filter(exploitation=exploitation).select_related("parcelle")
        if exploitation
        else Intervention.objects.none()
    )
    counts = {value: 0 for value, _label in Intervention.Type.choices}
    data = []
    for it in items:
        counts[it.intervention_type] = counts.get(it.intervention_type, 0) + 1
        data.append({
            "type": it.intervention_type,
            "typeLabel": it.get_intervention_type_display(),
            "title": it.title or it.get_intervention_type_display(),
            "date": it.start_time.strftime("%d/%m/%Y %H:%M") if it.start_time else "",
            "parcelle": it.parcelle.name if it.parcelle else "",
            "assignee": it.assigned_to.name if it.assigned_to else "",
            "status": it.get_status_display(),
        })
    parcelles = Parcelle.objects.filter(exploitation=exploitation) if exploitation else Parcelle.objects.none()
    members = TeamMember.objects.filter(exploitation=exploitation) if exploitation else TeamMember.objects.none()
    type_stats = []
    for value, label in Intervention.Type.choices:
        icon, color = TYPE_META.get(value, ("category", "slate"))
        type_stats.append({
            "key": value, "label": str(label), "count": counts.get(value, 0), "icon": icon,
            "chip": f"bg-{color}-100 text-{color}-600 dark:bg-{color}-500/15 dark:text-{color}-400",
            "ring": f"ring-{color}-400",
        })
    return render(request, "interventions/interventions.html", {
        "interventions_json": data,
        "counts": counts,
        "type_stats": type_stats,
        "total": len(data),
        "parcelles": parcelles,
        "members": members,
        "types": Intervention.Type.choices,
        "statuses": Intervention.Status.choices,
        "page_title": _("Interventions"),
    })


def _decimal(value):
    """Nombre saisi (« 3.5 » ou « 3,5 ») → float, ou None si vide/invalide."""
    value = (value or "").strip().replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return None


@login_required
@require_POST
def intervention_create(request):
    exploitation = _exploitation(request)
    itype = request.POST.get("intervention_type")
    # Parcelle obligatoire (marquée « * » dans le formulaire) : sans elle, on ne crée pas.
    parcelle = Parcelle.objects.filter(pk=request.POST.get("parcelle"), exploitation=exploitation).first()
    if exploitation and itype and parcelle:
        start = parse_datetime(request.POST.get("start_time") or "") or timezone.now()
        if timezone.is_naive(start):
            start = timezone.make_aware(start)
        member = TeamMember.objects.filter(pk=request.POST.get("assigned_to"), exploitation=exploitation).first()
        notes = (request.POST.get("notes") or "").strip()
        intervention = Intervention.objects.create(
            exploitation=exploitation,
            parcelle=parcelle,
            user=request.user,
            assigned_to=member,
            intervention_type=itype,
            start_time=start,
            duration_hours=_decimal(request.POST.get("duration_hours")),
            surface=_decimal(request.POST.get("surface")),
            cost=_decimal(request.POST.get("cost")),
            product=(request.POST.get("product") or "").strip(),
            dose=(request.POST.get("dose") or "").strip(),
            notes=notes,
        )
        # Toute intervention crée une tâche liée (visible dans « Tâches »),
        # assignée au même individu et échéancée à la date de l'intervention.
        title = f"{intervention.get_intervention_type_display()} — {parcelle.name}"
        task = Task.objects.create(
            exploitation=exploitation,
            title=title,
            description=notes,
            assigned_to=member,
            parcelle=parcelle,
            due_date=start,
            created_by=request.user,
        )
        intervention.title = title
        intervention.task = task
        intervention.save(update_fields=["title", "task"])
    return redirect("interventions:interventions")
