"""Parcelles agricoles et stades culturaux.

Fidèle aux tables Drizzle `parcelles` et `crop_stages` (cf. MIGRATION_PLAN §4).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel
from exploitations.models import Exploitation

# Champs culture/irrigation portés par ParcelleCampagne mais restant lisibles
# directement sur la parcelle (valeur de la campagne courante).
_CAMPAGNE_PROXY_FIELDS = (
    "culture", "variety", "kc_value", "tree_age_years", "planting_date",
    "plant_density_per_ha", "irrigation_type", "theoretical_flow_m3h",
    "nozzle_count", "nozzle_flow_lh", "row_spacing_m", "emitter_spacing_m",
    "service_pressure_bar",
)


def _campagne_proxy(field_name):
    """Propriété lecture seule déléguant à la campagne courante (ou None)."""

    def getter(self):
        campagne = self.campagne_courante
        return getattr(campagne, field_name) if campagne else None

    getter.__name__ = field_name
    return property(getter)


class Parcelle(TimeStampedModel):
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
    surface_utile = models.BooleanField(
        _("surface agricole utile (SAU)"), default=True,
        help_text=_("Cette surface compte-t-elle dans la SAU de l'exploitation ?"),
    )
    # Type d'agriculture au niveau parcelle (familles/sous-familles partagées
    # avec l'exploitation). Vide = « hérité de l'exploitation ».
    type_agriculture = models.CharField(
        _("type d'agriculture"), max_length=30, blank=True,
        choices=Exploitation.TYPE_AGRICULTURE_CHOICES,
        help_text=_("Laisser vide pour hériter du type d'agriculture de l'exploitation."),
    )

    # Géométrie
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    boundaries = models.JSONField(_("polygone"), null=True, blank=True)
    agro_polygon_id = models.CharField(max_length=100, blank=True)
    # Sens des rangs : azimut de la culture (0 = Nord, sens horaire). Se règle
    # sur la carte et s'y affiche comme une flèche au centre de la parcelle.
    orientation_rangs_deg = models.PositiveSmallIntegerField(
        _("sens des rangs (° / Nord)"), null=True, blank=True,
        help_text=_("0–359° (0 = Nord) — se règle sur la carte des parcelles."),
    )

    # Culture et irrigation sont désormais portées par ParcelleCampagne
    # (une campagne = une saison culturale, cf. ci-dessous).

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
    cadastre_data = models.JSONField(_("données cadastre (brut IGN)"), null=True, blank=True)
    acquired_at = models.DateTimeField(_("date d'acquisition"), null=True, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        verbose_name = _("parcelle")
        verbose_name_plural = _("parcelles")
        ordering = ("name",)
        indexes = [models.Index(fields=["exploitation", "status"])]

    def __str__(self):
        return str(self.name)

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("parcelles:detail", args=[self.pk])

    @property
    def type_agriculture_effectif(self):
        """Type d'agriculture de la parcelle, ou celui de l'exploitation si hérité."""
        return self.type_agriculture or self.exploitation.type_agriculture

    def get_type_agriculture_effectif_display(self):
        """Libellé lisible du type effectif (hérité inclus)."""
        value = self.type_agriculture_effectif
        for _group, options in Exploitation.TYPE_AGRICULTURE_CHOICES:
            for opt_value, label in options:
                if opt_value == value:
                    return label
        return ""

    @property
    def campagne_courante(self):
        """Campagne la plus récente (libellé le plus élevé), ou None."""
        if self.pk is None:
            return None
        return self.campagnes.first()

    # ── Accès direct depuis la parcelle (proxys vers la campagne courante) ──
    # culture, variety, kc_value, irrigation_type, etc. restent lisibles via
    # `parcelle.<champ>` comme avant le découpage en campagnes.
    locals().update({f: _campagne_proxy(f) for f in _CAMPAGNE_PROXY_FIELDS})

    def get_irrigation_type_display(self):
        campagne = self.campagne_courante
        return campagne.get_irrigation_type_display() if campagne else ""


class ParcelleCampagne(TimeStampedModel):
    """Culture et irrigation d'une parcelle pour une campagne agricole donnée.

    Une campagne est une saison culturale identifiée par un libellé année-année
    (ex. « 2025/2026 »). La culture et l'irrigation changent d'une campagne à
    l'autre (assolement / rotation), tandis que la parcelle (géométrie, sol,
    cadastre) reste stable.
    """

    class IrrigationType(models.TextChoices):
        GOUTTE = "goutte_a_goutte", _("Goutte à goutte")
        ASPERSION = "aspersion", _("Aspersion")
        ENROULEUR = "enrouleur", _("Enrouleur")
        PIVOT = "pivot", _("Pivot")
        MICRO_ASPERSION = "micro_aspersion", _("Micro-aspersion")
        GRAVITAIRE = "gravitaire", _("Gravitaire")

    parcelle = models.ForeignKey(
        Parcelle, on_delete=models.CASCADE, related_name="campagnes"
    )
    libelle = models.CharField(
        _("campagne"), max_length=20,
        help_text=_("Libellé année-année, ex. « 2025/2026 »."),
    )

    # Culture
    type_culture = models.CharField(
        _("type de culture"), max_length=20, blank=True,
        help_text=_("Déduit de la culture choisie si laissé vide."),
    )
    culture = models.CharField(_("culture"), max_length=100, blank=True)
    variety = models.CharField(_("variété"), max_length=100, blank=True)
    kc_value = models.FloatField(_("coefficient Kc"), default=1.0)
    tree_age_years = models.IntegerField(_("âge des plants (ans)"), null=True, blank=True)
    planting_date = models.DateField(_("date de plantation"), null=True, blank=True)
    plant_density_per_ha = models.IntegerField(_("densité (pieds/ha)"), null=True, blank=True)

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

    class Meta:
        verbose_name = _("campagne de parcelle")
        verbose_name_plural = _("campagnes de parcelle")
        ordering = ("-libelle",)
        constraints = [
            models.UniqueConstraint(
                fields=["parcelle", "libelle"], name="unique_parcelle_campagne"
            )
        ]

    def __str__(self):
        return f"{self.parcelle.name} — {self.libelle}"

    # Le référentiel des types de culture vit dans `agronomie.CultureKc` : on le
    # lit à la volée plutôt que de figer ses catégories dans une migration.
    @staticmethod
    def types_culture():
        from agronomie.models import CultureKc

        return CultureKc.Categorie.choices

    @staticmethod
    def type_culture_de(culture):
        """Catégorie de la culture d'après le référentiel (vide si inconnue)."""
        from agronomie.models import CultureKc

        if not (culture or "").strip():
            return ""
        fiche = CultureKc.objects.filter(nom__iexact=culture.strip()).first()
        return fiche.categorie if fiche else ""

    @property
    def type_culture_label(self):
        return dict(self.types_culture()).get(self.type_culture, self.type_culture)

    @staticmethod
    def libelle_courant(today=None):
        """Libellé de la campagne en cours pour une date donnée (défaut : aujourd'hui).

        Convention de l'exploitation : la campagne va de septembre à septembre.
        Une date d'août 2026 relève donc encore de la campagne « 2025/2026 »,
        et septembre 2026 ouvre la campagne « 2026/2027 ».
        """
        from django.utils import timezone

        today = today or timezone.localdate()
        start_year = today.year if today.month >= 9 else today.year - 1
        return f"{start_year}/{start_year + 1}"


class CropStage(TimeStampedModel):
    """Stade phénologique d'une culture (campagne) avec coefficient Kc."""

    parcelle_campagne = models.ForeignKey(
        ParcelleCampagne, on_delete=models.CASCADE, related_name="crop_stages",
    )
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
