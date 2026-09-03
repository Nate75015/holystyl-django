"""Tâches Celery équipe : rappels d'échéance (parité taskReminderJob.ts)."""

from datetime import timedelta

from celery import shared_task
from django.core.mail import send_mail
from django.utils import timezone

from core.sms import send_sms


@shared_task
def check_task_reminders():
    """Envoie les rappels 24h et 1h avant l'échéance (email + SMS).

    Exécuté toutes les 15 min par Celery Beat. Idempotent grâce aux flags.
    """
    from .models import Task

    now = timezone.now()
    sent = {"email": 0, "sms": 0}

    # Rappel 24h : échéance dans 23h-25h
    window_24 = Task.objects.filter(
        due_date__gte=now + timedelta(hours=23),
        due_date__lte=now + timedelta(hours=25),
        reminder_sent_24h=False,
    ).exclude(status__in=["done", "validated"])
    for task in window_24:
        sent["email"] += _send_reminder(task, "24h")
        task.reminder_sent_24h = True
        task.save(update_fields=["reminder_sent_24h"])

    # Rappel 1h : échéance dans 30min-1h30
    window_1 = Task.objects.filter(
        due_date__gte=now + timedelta(minutes=30),
        due_date__lte=now + timedelta(minutes=90),
        reminder_sent_1h=False,
    ).exclude(status__in=["done", "validated"])
    for task in window_1:
        sent["email"] += _send_reminder(task, "1h")
        task.reminder_sent_1h = True
        task.save(update_fields=["reminder_sent_1h"])

    return sent


def _send_reminder(task, horizon: str) -> int:
    member = task.assigned_to
    if member is None:
        return 0
    msg = f"Rappel ({horizon}) — tâche « {task.title} » à échéance {task.due_date:%d/%m %H:%M}."
    count = 0
    if member.email:
        send_mail("Rappel de tâche Isidor", msg, None, [member.email], fail_silently=True)
        count = 1
    if member.phone:
        send_sms(member.phone, msg)
    return count
