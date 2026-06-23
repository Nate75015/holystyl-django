"""Application Celery — jobs planifiés (rapport quotidien, rappels) et tâches async."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("holystyl")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Tâches périodiques (équivalent des cron Node) — branchées au fil des tranches :
#   - rapport quotidien DTI à 21h00 (Tranche 3)
#   - rappels de tâches toutes les 15 min (Tranche 4)
app.conf.beat_schedule = {}
