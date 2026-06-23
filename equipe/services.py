"""Services équipe : notification SMS d'affectation, lien de géolocalisation."""

import secrets
from datetime import timedelta

from django.utils import timezone

from core.sms import send_sms


def notify_task_assignment(task) -> bool:
    """Envoie un SMS au membre assigné lors de la création/affectation d'une tâche."""
    member = task.assigned_to
    if member is None or not member.phone:
        return False
    due = f" (échéance {task.due_date:%d/%m %H:%M})" if task.due_date else ""
    body = f"Holystyl — Nouvelle tâche : « {task.title} »{due}."
    return send_sms(member.phone, body)


def generate_location_link(member) -> str:
    """Génère un token de partage de position valable 24h (parité team.generateLocationLink)."""
    member.location_token = secrets.token_urlsafe(32)
    member.location_token_expires_at = timezone.now() + timedelta(hours=24)
    member.save(update_fields=["location_token", "location_token_expires_at"])
    return member.location_token
