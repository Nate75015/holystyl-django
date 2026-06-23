"""Réglages de développement."""

from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Channels en mémoire, Celery synchrone : aucun Redis requis en dev.
CELERY_TASK_ALWAYS_EAGER = True

# Emails affichés en console.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
