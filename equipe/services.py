"""Services équipe : SMS d'affectation, lien de géolocalisation, tâches filles."""

import json
import secrets
from datetime import datetime, timedelta

from django.utils import timezone
from django.utils.dateparse import parse_date

from core.sms import send_sms


def notify_task_assignment(task) -> bool:
    """Envoie un SMS au membre assigné lors de la création/affectation d'une tâche."""
    member = task.assigned_to
    if member is None or not member.phone:
        return False
    due = f" (échéance {task.due_date:%d/%m %H:%M})" if task.due_date else ""
    body = f"Isidor — Nouvelle tâche : « {task.title} »{due}."
    return send_sms(member.phone, body)


def generate_location_link(member) -> str:
    """Génère un token de partage de position valable 24h (parité team.generateLocationLink)."""
    member.location_token = secrets.token_urlsafe(32)
    member.location_token_expires_at = timezone.now() + timedelta(hours=24)
    member.save(update_fields=["location_token", "location_token_expires_at"])
    return member.location_token


# ── Accès pour les tableaux de bord ─────────────────────────────────────


def compte_membres(exploitation) -> int:
    """Nombre de membres d'équipe de l'exploitation (ETP affiché sur Pulse)."""
    if exploitation is None:
        return 0
    from .models import TeamMember

    return TeamMember.objects.filter(exploitation=exploitation).count()


def membre_de(user):
    """Le membre d'équipe actif rattaché à ce compte, ou None."""
    if user is None or not user.is_authenticated:
        return None
    from .models import TeamMember

    return TeamMember.objects.filter(user=user, is_active=True).first()


def taches_du_membre(membre, limite=10):
    """Les tâches en cours assignées au membre, les plus urgentes d'abord."""
    if membre is None:
        return []
    from .models import Task

    return list(
        Task.objects.filter(assigned_to=membre)
        .exclude(status__in=[Task.Status.DONE, Task.Status.VALIDATED])
        .prefetch_related("parcelles")
        .order_by("due_date", "-created_at")[:limite]
    )


def _minuit(jour):
    """Un jour → datetime aware à minuit, ou None."""
    return timezone.make_aware(datetime.combine(jour, datetime.min.time())) if jour else None


def enregistrer_parcelles(task, request, exploitation):
    """Applique la sélection de parcelles postée par les pastilles.

    `parcelle` garde la première : l'API et l'espace employé lisent ce champ
    simple là où l'interface manipule une sélection multiple.
    """
    from parcelles.models import Parcelle

    choisies = list(
        Parcelle.objects.filter(pk__in=request.POST.getlist("parcelles"),
                                exploitation=exploitation).order_by("name"))
    task.parcelle = choisies[0] if choisies else None
    task.save(update_fields=["parcelle"])
    task.parcelles.set(choisies)
    return choisies


def enregistrer_sous_taches(task, request, exploitation):
    """Synchronise les tâches filles depuis le JSON du champ caché `subtasks`.

    Une sous-tâche est une tâche à part entière : elle a son assigné, sa date et
    son statut. Les lignes retirées côté formulaire sont supprimées.

    Partagé par la modale du planning et le formulaire de tâches : les deux
    créent la même chose, elles doivent la créer de la même façon.
    """
    from .models import Task, TeamMember

    try:
        rows = json.loads(request.POST.get("subtasks") or "[]")
    except json.JSONDecodeError:
        return
    if not isinstance(rows, list):
        return

    gardees = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        titre = (row.get("title") or "").strip()
        if not titre:
            continue
        try:
            sous_id = int(row.get("id") or 0)
        except (TypeError, ValueError):
            sous_id = 0
        sous = (Task.objects.filter(pk=sous_id, parent=task, exploitation=exploitation).first()
                if sous_id else None)
        if sous is None:
            sous = Task(exploitation=exploitation, parent=task,
                        created_by=request.user, priority=task.priority)
        sous.title = titre[:255]
        if row.get("done"):
            sous.status = Task.Status.DONE
        elif sous.is_done:
            sous.status = Task.Status.TODO
        sous.assigned_to = (
            TeamMember.objects.filter(pk=row.get("member") or None,
                                      exploitation=exploitation).first()
            or task.assigned_to)
        jour = parse_date(str(row.get("date") or ""))
        sous.start_date = sous.due_date = _minuit(jour)
        sous.save()
        gardees.append(sous.pk)
    task.subtasks.exclude(pk__in=gardees).delete()
