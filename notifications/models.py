"""Centre de notifications et règles d'alerte.

Fidèle aux tables Drizzle `notifications`, `notification_rules`.
Le canal (push/email/sms/whatsapp) est stocké dans `channels` (JSON).
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Notification(models.Model):
    class Priority(models.TextChoices):
        BASSE = "basse", _("Basse")
        NORMALE = "normale", _("Normale")
        HAUTE = "haute", _("Haute")
        URGENTE = "urgente", _("Urgente")

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=50)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMALE)
    title = models.CharField(max_length=255)
    message = models.TextField()
    read = models.BooleanField(default=False)
    action_url = models.CharField(max_length=500, blank=True)
    parcelle = models.ForeignKey("parcelles.Parcelle", on_delete=models.SET_NULL, null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("notification")
        verbose_name_plural = _("notifications")
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["user", "-created_at"])]


class NotificationRule(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_rules")
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=50)
    condition_type = models.CharField(max_length=50)
    threshold = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    enabled = models.BooleanField(default=True)
    channels = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("règle de notification")
        verbose_name_plural = _("règles de notification")
        ordering = ("name",)
