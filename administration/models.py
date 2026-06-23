"""Configuration SMTP par exploitation (espace Admin).

Fidèle à la table Drizzle `smtp_config`.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


class SmtpConfig(TimeStampedModel):
    class TestStatus(models.TextChoices):
        OK = "ok", "OK"
        ERROR = "error", _("Erreur")

    exploitation = models.OneToOneField("exploitations.Exploitation", on_delete=models.CASCADE, related_name="smtp_config")
    host = models.CharField(max_length=255)
    port = models.IntegerField(default=587)
    secure = models.BooleanField(default=False)  # True = SSL/465, False = TLS/STARTTLS
    user = models.CharField(max_length=320)
    password = models.TextField()
    from_name = models.CharField(max_length=255, default="Holystyl")
    from_email = models.EmailField()
    enabled = models.BooleanField(default=True)
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_status = models.CharField(max_length=8, choices=TestStatus.choices, blank=True)
    last_test_error = models.TextField(blank=True)

    class Meta:
        verbose_name = _("configuration SMTP")
        verbose_name_plural = _("configurations SMTP")

    def __str__(self):
        return f"SMTP {self.host} ({self.exploitation})"
