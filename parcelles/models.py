"""Parcelles agricoles et stades culturaux.

Fidèle aux tables Drizzle `parcelles` et `crop_stages` (cf. MIGRATION_PLAN §4).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


class Parcelle(TimeStampedModel):
    class IrrigationType(models.TextChoices):
        GOUTTE = "goutte_a_goutte", _("Goutte à goutte")
        ASPERSION = "aspersion", _("Aspersion")
        ENROULEUR = "enrouleur", _("Enrouleur")
        PIVOT = "pivot", _("Pivot")
        MICRO_ASPERSION = "micro_aspersion", _("Micro-aspersion")
        GRAVITAIRE = "gravitaire", _("Gravitaire")

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        INACTIVE = "inactive", _("Inactive")
        JACHERE = "jachere", _("Jachère")

    exploitation = models.ForeignKey(
        "exploitations.Exploitation",
        on_delete=models.CASCADE,
        related_name="parcelles",
    )
    name = models.CharField(_("nom"), max_length=255)
    area = models.FloatField(_("surface (ha)"), null=True, blank=True)

    # Géométrie
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    boundaries = models.JSONField(_("polygone"), null=True, blank=True)
    agro_polygon_id = models.CharField(max_length=100, blank=True)

    # Irrigation
    irrigation_type = models.CharField(
        _("type d'irrigation"), max_length=20, choices=IrrigationType.choices, blank=True
    )
    theoretical_flow_m3h = models.FloatField(_("débit théorique (m³/h)"), null=True, blank=True)
    nozzle_count = models.IntegerField(_("nombre de buses"), null=True, blank=True)
    nozzle_flow_lh = models.FloatField(_("débit buse (L/h)"), null=True, blank=True)
    row_spacing_m = models.FloatField(_("écart entre rangs (m)"), null=True, blank=True)
    emitter_spacing_m = models.FloatField(_("écart entre émetteurs (m)"), null=True, blank=True)
    service_pressure_bar = models.FloatField(_("pression de service (bar)"), null=True, blank=True)

    # Culture
    culture = models.CharField(_("culture"), max_length=100, blank=True)
    variety = models.CharField(_("variété"), max_length=100, blank=True)
    kc_value = models.FloatField(_("coefficient Kc"), default=1.0)
    tree_age_years = models.IntegerField(_("âge des plants (ans)"), null=True, blank=True)
    planting_date = models.DateField(_("date de plantation"), null=True, blank=True)
    plant_density_per_ha = models.IntegerField(_("densité (pieds/ha)"), null=True, blank=True)

    # Sol
    soil_type = models.CharField(_("type de sol"), max_length=100, blank=True)
    root_depth = models.FloatField(_("profondeur racinaire"), null=True, blank=True)
    root_depth_cm = models.IntegerField(_("profondeur racinaire (cm)"), null=True, blank=True)
    soil_retention_mm_m = models.FloatField(_("rétention sol (mm/m)"), null=True, blank=True)
    soil_ph = models.FloatField(_("pH du sol"), null=True, blank=True)

    # Administratif
    cadastral_ref = models.CharField(_("réf. cadastrale"), max_length=50, blank=True)
    commune = models.CharField(_("commune"), max_length=100, blank=True)
    official_area_ha = models.FloatField(_("surface officielle (ha)"), null=True, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        verbose_name = _("parcelle")
        verbose_name_plural = _("parcelles")
        ordering = ("name",)
        indexes = [models.Index(fields=["exploitation", "status"])]

    def __str__(self):
        return self.name


class CropStage(TimeStampedModel):
    """Stade phénologique d'une parcelle avec coefficient Kc."""

    parcelle = models.ForeignKey(Parcelle, on_delete=models.CASCADE, related_name="crop_stages")
    stage_name = models.CharField(_("stade"), max_length=100)
    stage_code = models.CharField(max_length=20, blank=True)
    start_date = models.DateField(_("début"))
    end_date = models.DateField(_("fin"), null=True, blank=True)
    kc_value = models.FloatField(_("coefficient Kc"))
    root_depth_m = models.FloatField(_("profondeur racinaire (m)"), null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("stade cultural")
        verbose_name_plural = _("stades culturaux")
        ordering = ("start_date",)

    def __str__(self):
        return f"{self.stage_name} ({self.parcelle.name})"
