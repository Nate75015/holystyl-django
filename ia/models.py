"""Assistant IA : conversations, dictionnaire vocal, rapports quotidiens.

Fidèle aux tables Drizzle `ai_conversations`, `vocal_dictionary`, `daily_reports`.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AiConversation(models.Model):
    class Role(models.TextChoices):
        USER = "user", _("Utilisateur")
        ASSISTANT = "assistant", _("Assistant")

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="ai_conversations")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    thread = models.UUIDField(null=True, blank=True, db_index=True)
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    audio_url = models.TextField(blank=True)
    extracted_action = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("conversation IA")
        verbose_name_plural = _("conversations IA")
        ordering = ("created_at",)


class VocalDictionary(models.Model):
    class Category(models.TextChoices):
        PARCELLE = "parcelle", _("Parcelle")
        CULTURE = "culture", _("Culture")
        MATERIEL = "materiel", _("Matériel")
        PRODUIT = "produit", _("Produit")
        GENERAL = "general", _("Général")

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="vocal_dictionary")
    term = models.CharField(max_length=255)
    replacement = models.CharField(max_length=255)
    category = models.CharField(max_length=12, choices=Category.choices, default=Category.GENERAL)

    class Meta:
        verbose_name = _("terme vocal")
        verbose_name_plural = _("dictionnaire vocal")


class DailyReport(models.Model):
    class DtiScore(models.TextChoices):
        A = "A", "A"
        B = "B", "B"
        C = "C", "C"
        D = "D", "D"

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="daily_reports")
    report_date = models.DateField()
    summary = models.TextField(blank=True)
    dti_score = models.CharField(max_length=1, choices=DtiScore.choices, blank=True)
    kwh_per_m3 = models.FloatField(null=True, blank=True)
    water_used_m3 = models.FloatField(null=True, blank=True)
    energy_used_kwh = models.FloatField(null=True, blank=True)
    alerts_count = models.IntegerField(default=0)
    recommendations = models.JSONField(null=True, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("rapport quotidien")
        verbose_name_plural = _("rapports quotidiens")
        ordering = ("-report_date",)
