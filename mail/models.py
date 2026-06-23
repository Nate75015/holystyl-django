"""Mail : envoi de vrais e-mails (SMTP) + historique des envois."""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


class Email(TimeStampedModel):
    """Trace d'un e-mail sortant envoyé depuis l'app."""

    class Status(models.TextChoices):
        SENT = "sent", _("Envoyé")
        FAILED = "failed", _("Échec")

    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="emails",
    )
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    to = models.TextField(_("destinataires"))
    cc = models.TextField(_("copie"), blank=True)
    subject = models.CharField(_("objet"), max_length=255)
    body = models.TextField(_("message"))
    attachments = models.JSONField(_("pièces jointes"), default=list, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SENT)
    error = models.TextField(blank=True)

    class Meta:
        verbose_name = _("e-mail")
        verbose_name_plural = _("e-mails")
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.subject} → {self.to}"

    @property
    def to_list(self):
        return [a for a in self.to.replace("\n", ",").split(",") if a.strip()]
