"""Tâches Celery IA : rapport quotidien (parité scheduler.ts, 21h)."""

from celery import shared_task


@shared_task
def generate_daily_reports():
    """Génère le rapport quotidien pour chaque exploitation (exécuté à 21h)."""
    from exploitations.models import Exploitation

    from .services import generate_daily_report

    count = 0
    for exploitation in Exploitation.objects.all():
        generate_daily_report(exploitation)
        count += 1
    return count
