"""Interventions terrain — journal des opérations culturales."""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


class Intervention(TimeStampedModel):
    class Type(models.TextChoices):
        IRRIGATION = "irrigation", _("Irrigation")
        TRAITEMENT = "traitement", _("Traitement")
        FERTILISATION = "fertilisation", _("Fertilisation")
        RECOLTE = "recolte", _("Récolte")
        SEMIS = "semis", _("Semis")
        TRAVAIL_SOL = "travail_sol", _("Travail du sol")
        TAILLE = "taille", _("Taille")
        PALISSAGE = "palissage", _("Palissage")
        DESHERBAGE = "desherbage", _("Désherbage")
        ECLAIRCISSAGE = "eclaircissage", _("Éclaircissage")
        EFFEUILLAGE = "effeuillage", _("Effeuillage")
        VENDANGE = "vendange", _("Vendange")
        MAINTENANCE = "maintenance", _("Maintenance")
        OBSERVATION = "observation", _("Observation")
        AUTRE = "autre", _("Autre")

    class Status(models.TextChoices):
        PLANIFIEE = "planifiee", _("Planifiée")
        EN_COURS = "en_cours", _("En cours")
        TERMINEE = "terminee", _("Terminée")
        ANNULEE = "annulee", _("Annulée")

    class Source(models.TextChoices):
        VOICE = "voice", _("Vocal")
        MANUAL = "manual", _("Manuel")
        AI = "ai", _("IA")

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="interventions")
    parcelle = models.ForeignKey("parcelles.Parcelle", on_delete=models.SET_NULL, null=True, blank=True)
    machine = models.ForeignKey("operations.Machine", on_delete=models.SET_NULL, null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    assigned_to = models.ForeignKey("equipe.TeamMember", on_delete=models.SET_NULL, null=True, blank=True)
    task = models.ForeignKey("equipe.Task", on_delete=models.SET_NULL, null=True, blank=True)
    intervention_type = models.CharField(max_length=15, choices=Type.choices)
    title = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PLANIFIEE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    duration_hours = models.FloatField(null=True, blank=True)
    product = models.CharField(max_length=255, blank=True)
    dose = models.CharField(max_length=100, blank=True)
    unit = models.CharField(max_length=50, blank=True)
    surface = models.FloatField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    notes = models.TextField(blank=True)
    voice_transcript = models.TextField(blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MANUAL)

    class Meta:
        verbose_name = _("intervention")
        verbose_name_plural = _("interventions")
        ordering = ("-start_time",)
        indexes = [models.Index(fields=["exploitation", "-start_time"])]

    def __str__(self):
        return self.title or self.get_intervention_type_display()
