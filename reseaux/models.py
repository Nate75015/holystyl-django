"""Réseau professionnel : connexions entre utilisateurs (type LinkedIn).

Une connexion doit être demandée puis acceptée. La messagerie n'autorise le
contact qu'entre personnes connectées (statut « acceptée »).
"""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


class Connexion(TimeStampedModel):
    """Lien de réseau entre deux utilisateurs : demande → acceptation."""

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", _("En attente")
        ACCEPTEE = "acceptee", _("Acceptée")
        REFUSEE = "refusee", _("Refusée")

    demandeur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="connexions_envoyees",
        verbose_name=_("demandeur"),
    )
    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="connexions_recues",
        verbose_name=_("destinataire"),
    )
    statut = models.CharField(_("statut"), max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE)
    message = models.CharField(_("message de connexion"), max_length=280, blank=True)
    responded_at = models.DateTimeField(_("répondu le"), null=True, blank=True)

    class Meta:
        verbose_name = _("connexion")
        verbose_name_plural = _("connexions")
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(fields=["demandeur", "destinataire"], name="uniq_connexion_paire"),
        ]
        indexes = [
            models.Index(fields=["destinataire", "statut"]),
            models.Index(fields=["demandeur", "statut"]),
        ]

    def __str__(self):
        return f"{self.demandeur_id} → {self.destinataire_id} ({self.statut})"

    # ── Helpers ──────────────────────────────────────────────────────
    @classmethod
    def between(cls, user_a, user_b):
        """La connexion existante entre deux users (dans un sens ou l'autre), ou None."""
        return cls.objects.filter(
            Q(demandeur=user_a, destinataire=user_b) | Q(demandeur=user_b, destinataire=user_a)
        ).first()

    @classmethod
    def are_connected(cls, user_a, user_b) -> bool:
        """Vrai si les deux users sont connectés (demande acceptée)."""
        return cls.objects.filter(
            statut=cls.Statut.ACCEPTEE
        ).filter(
            Q(demandeur=user_a, destinataire=user_b) | Q(demandeur=user_b, destinataire=user_a)
        ).exists()

    @classmethod
    def connected_user_ids(cls, user):
        """IDs des utilisateurs connectés (acceptés) à `user`."""
        ids = set()
        for c in cls.objects.filter(statut=cls.Statut.ACCEPTEE).filter(
            Q(demandeur=user) | Q(destinataire=user)
        ).values_list("demandeur_id", "destinataire_id"):
            ids.update(c)
        ids.discard(user.id)
        return ids
