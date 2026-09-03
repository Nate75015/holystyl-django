"""Application Celery — jobs planifiés (rapport quotidien, rappels) et tâches async."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("isidor")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Tâches périodiques (équivalent des cron Node : scheduler.ts + taskReminderJob.ts)
from celery.schedules import crontab  # noqa: E402

app.conf.beat_schedule = {
    "task-reminders-every-15min": {
        "task": "equipe.tasks.check_task_reminders",
        "schedule": 15 * 60,  # toutes les 15 minutes
    },
    "daily-report-21h": {
        "task": "ia.tasks.generate_daily_reports",
        "schedule": crontab(hour=21, minute=0),
    },
    "evaluate-notification-rules-hourly": {
        "task": "notifications.tasks.evaluate_rules",
        "schedule": crontab(minute=0),  # à chaque heure pile
    },
}
