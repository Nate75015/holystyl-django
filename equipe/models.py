"""Équipe et tâches.

Fidèle aux tables Drizzle `team_members`, `tasks`, `task_reminders`.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


class TeamMember(TimeStampedModel):
    class Role(models.TextChoices):
        ASSOCIE = "associe", _("Associé")
        CHEF = "chef", _("Chef d'équipe")
        OUVRIER = "ouvrier", _("Ouvrier")
        SAISONNIER = "saisonnier", _("Saisonnier")
        PRESTATAIRE = "prestataire", _("Prestataire")

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="team_members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(_("nom"), max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(_("téléphone"), max_length=30, blank=True)
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.OUVRIER)
    color = models.CharField(max_length=7, default="#29738f")
    is_active = models.BooleanField(default=True)
    is_online = models.BooleanField(default=False)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    location_token = models.CharField(max_length=64, blank=True)
    location_token_expires_at = models.DateTimeField(null=True, blank=True)
    password_hash = models.CharField(max_length=255, blank=True)
    allowed_modules = models.JSONField(default=list, blank=True)
    preferred_locale = models.CharField(max_length=5, default="fr")
    managed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="managed_members"
    )

    class Meta:
        verbose_name = _("membre d'équipe")
        verbose_name_plural = _("membres d'équipe")
        ordering = ("name",)

    def __str__(self):
        return self.name


class Task(TimeStampedModel):
    class Priority(models.TextChoices):
        HAUTE = "haute", _("Haute")
        NORMALE = "normale", _("Normale")
        BASSE = "basse", _("Basse")

    class Status(models.TextChoices):
        TODO = "todo", _("À faire")
        INPROGRESS = "inprogress", _("En cours")
        DONE = "done", _("Terminée")
        VALIDATED = "validated", _("Validée")

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(_("titre"), max_length=255)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(TeamMember, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")
    parcelle = models.ForeignKey("parcelles.Parcelle", on_delete=models.SET_NULL, null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMALE)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.TODO)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    reminder_sent_24h = models.BooleanField(default=False)
    reminder_sent_1h = models.BooleanField(default=False)
    sms_sent_24h = models.BooleanField(default=False)
    sms_sent_1h = models.BooleanField(default=False)

    class Meta:
        verbose_name = _("tâche")
        verbose_name_plural = _("tâches")
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["exploitation", "status"])]

    def __str__(self):
        return self.title


class TaskReminder(models.Model):
    class Type(models.TextChoices):
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"

    class Status(models.TextChoices):
        PENDING = "pending", _("En attente")
        SENT = "sent", _("Envoyé")
        FAILED = "failed", _("Échoué")

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="reminders")
    type = models.CharField(max_length=10, choices=Type.choices)
    scheduled_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("rappel de tâche")
        verbose_name_plural = _("rappels de tâche")
