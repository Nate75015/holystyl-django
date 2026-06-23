"""Modèles de base réutilisables par toutes les apps métier."""

from django.db import models


class TimeStampedModel(models.Model):
    """Ajoute created_at / updated_at (équivalent des timestamps Drizzle)."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ("-created_at",)
