"""Capture de leads (lead magnet, agent commercial).

Fidèle à la table Drizzle `lead_captures`.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class LeadCapture(models.Model):
    email = models.EmailField()
    source = models.CharField(max_length=64, default="guide_analyses")
    guide_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("lead capturé")
        verbose_name_plural = _("leads capturés")
        ordering = ("-created_at",)

    def __str__(self):
        return self.email
