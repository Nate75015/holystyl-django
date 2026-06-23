"""Création de notifications (utilisé par les alertes, jobs, IA…)."""

from .models import Notification


def notify(user, *, type: str, title: str, message: str, priority="normale", action_url="", parcelle=None, metadata=None):
    return Notification.objects.create(
        user=user,
        type=type,
        title=title,
        message=message,
        priority=priority,
        action_url=action_url,
        parcelle=parcelle,
        metadata=metadata,
    )
