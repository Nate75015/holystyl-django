"""Laboratoire & analyses : rapports OCR, analyses de sol, biodiversité.

Fidèle aux tables Drizzle `analysis_results`, `analyses_sol`, `biodiversite_fiches`.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class AnalysisResult(models.Model):
    """Rapport d'analyse uploadé (PDF) avec extraction OCR + IA."""

    class AnalysisType(models.TextChoices):
        SOIL = "soil", _("Sol")
        WATER = "water", _("Eau")
        LEAF = "leaf", _("Foliaire")
        PLANT = "plant", _("Plante")

    class Status(models.TextChoices):
        PENDING_OCR = "pending_ocr", _("OCR en attente")
        OCR_DONE = "ocr_done", _("OCR effectué")
        VALIDATED = "validated", _("Validé")

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="analysis_results")
    parcelle = models.ForeignKey("parcelles.Parcelle", on_delete=models.SET_NULL, null=True, blank=True)
    analysis_type = models.CharField(max_length=10, choices=AnalysisType.choices)
    sample_date = models.DateTimeField()
    lab_name = models.CharField(max_length=255, blank=True)
    file_url = models.TextField(blank=True)
    file_key = models.TextField(blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    ocr_raw_text = models.TextField(blank=True)
    parsed_data = models.JSONField(null=True, blank=True)
    ph = models.FloatField(null=True, blank=True)
    organic_matter_pct = models.FloatField(null=True, blank=True)
    nitrogen_mg_kg = models.FloatField(null=True, blank=True)
    phosphorus_mg_kg = models.FloatField(null=True, blank=True)
    potassium_mg_kg = models.FloatField(null=True, blank=True)
    electrical_conductivity = models.FloatField(null=True, blank=True)
    recommendations = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING_OCR)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("rapport d'analyse")
        verbose_name_plural = _("rapports d'analyse")
        ordering = ("-sample_date",)


class BiodiversiteFiche(models.Model):
    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="biodiversite_fiches")
    parcelle = models.ForeignKey("parcelles.Parcelle", on_delete=models.CASCADE, related_name="biodiversite_fiches")
    saison = models.ForeignKey("agronomie.Saison", on_delete=models.SET_NULL, null=True, blank=True)
    score = models.FloatField(default=0)
    nb_especes_vegetales = models.IntegerField(default=0)
    nb_especes_animales = models.IntegerField(default=0)
    haies_ml = models.FloatField(default=0)
    jachere_ha = models.FloatField(default=0)
    observations = models.TextField(blank=True)
    date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("fiche biodiversité")
        verbose_name_plural = _("fiches biodiversité")
        ordering = ("-date",)
