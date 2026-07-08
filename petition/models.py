"""Pétitions : un texte à soutenir, une signature par utilisateur, objectif optionnel."""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


class Petition(TimeStampedModel):
    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE,
        null=True, blank=True, related_name="petitions",
    )
    title = models.CharField(_("titre"), max_length=255)
    description = models.TextField(_("description"), blank=True)
    goal = models.PositiveIntegerField(_("objectif de signatures"), default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )
    closed = models.BooleanField(_("clôturée"), default=False)

    class Meta:
        verbose_name = _("pétition")
        verbose_name_plural = _("pétitions")
        ordering = ("-created_at",)

    def __str__(self):
        return self.title

    def signature_count(self):
        return self.signatures.count()

    def user_signed(self, user):
        """L'utilisateur a-t-il déjà signé ?"""
        return self.signatures.filter(user=user).exists()

    def progress_pct(self):
        """Progression vers l'objectif (0-100), ou None si aucun objectif."""
        if not self.goal:
            return None
        return min(100, round(self.signature_count() * 100 / self.goal))


class Signature(TimeStampedModel):
    petition = models.ForeignKey(Petition, on_delete=models.CASCADE, related_name="signatures")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    comment = models.CharField(_("commentaire"), max_length=280, blank=True)

    class Meta:
        verbose_name = _("signature")
        verbose_name_plural = _("signatures")
        ordering = ("-created_at",)
        unique_together = ("petition", "user")

    def __str__(self):
        return f"{self.user} → {self.petition}"
