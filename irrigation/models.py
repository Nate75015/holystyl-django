"""Pilotage hydrique : irrigation, eau, énergie, quotas, DTI, gel, NDVI.

Fidèle aux tables Drizzle : irrigation_zones, irrigation_programs,
irrigation_sessions, pumping_stations, bassinage_events, water_meters,
energy_logs, water_quotas, dti_scores, frost_events, ndvi_data,
invisible_loss_detections (cf. MIGRATION_PLAN §4).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel

EXPLOITATION_FK = dict(on_delete=models.CASCADE)


# ── Irrigation ──────────────────────────────────────────────────────────────
class IrrigationZone(TimeStampedModel):
    class IrrigationType(models.TextChoices):
        GOUTTE = "goutte_a_goutte", _("Goutte à goutte")
        ASPERSION = "aspersion", _("Aspersion")
        PIVOT = "pivot", _("Pivot")
        ENROULEUR = "enrouleur", _("Enrouleur")
        MICRO_ASPERSION = "micro_aspersion", _("Micro-aspersion")
        MICRO_JET = "micro_jet", _("Micro-jet")
        SUBMERSION = "submersion", _("Submersion")

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        INACTIVE = "inactive", _("Inactive")
        MAINTENANCE = "maintenance", _("Maintenance")

    exploitation = models.ForeignKey("exploitations.Exploitation", related_name="irrigation_zones", **EXPLOITATION_FK)
    # Une zone peut couvrir plusieurs parcelles (ex. un même réseau sur plusieurs îlots).
    parcelles = models.ManyToManyField("parcelles.Parcelle", related_name="irrigation_zones", blank=True)
    name = models.CharField(max_length=255)
    irrigation_type = models.CharField(max_length=20, choices=IrrigationType.choices, default=IrrigationType.GOUTTE)
    flow_rate_m3h = models.FloatField(null=True, blank=True)
    surface_ha = models.FloatField(null=True, blank=True)
    vanne_id = models.CharField(max_length=100, blank=True)
    programmateur_id = models.CharField(max_length=100, blank=True)
    service_pressure_bar = models.FloatField(null=True, blank=True)
    auto_regulation = models.BooleanField(default=False)
    pluviometry_mm_h = models.FloatField(null=True, blank=True)
    emitter_flow_lh = models.FloatField(null=True, blank=True)
    row_spacing_m = models.FloatField(null=True, blank=True)
    emitter_spacing_m = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        verbose_name = _("zone d'irrigation")
        verbose_name_plural = _("zones d'irrigation")
        ordering = ("name",)

    def __str__(self):
        return self.name


class IrrigationProgram(TimeStampedModel):
    class Frequency(models.TextChoices):
        DAILY = "daily", _("Quotidien")
        EVERY_2 = "every_2_days", _("Tous les 2 jours")
        EVERY_3 = "every_3_days", _("Tous les 3 jours")
        WEEKLY = "weekly", _("Hebdomadaire")
        CUSTOM = "custom", _("Personnalisé")

    class Mode(models.TextChoices):
        TIME = "time", _("Par durée")
        VOLUME = "volume", _("Par volume")
        PLUVIOMETRY = "pluviometry", _("Par pluviométrie")

    class CreatedBy(models.TextChoices):
        MANUAL = "manual", _("Manuel")
        VOICE = "voice", _("Vocal")
        AI = "ai", _("IA")

    exploitation = models.ForeignKey("exploitations.Exploitation", related_name="irrigation_programs", **EXPLOITATION_FK)
    # Un programme peut piloter plusieurs parcelles (même horaire/durée sur plusieurs îlots).
    parcelles = models.ManyToManyField("parcelles.Parcelle", related_name="irrigation_programs", blank=True)
    zone = models.ForeignKey(IrrigationZone, related_name="programs", on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255)
    start_hour = models.IntegerField()
    start_minute = models.IntegerField(default=0)
    duration_minutes = models.IntegerField()
    frequency = models.CharField(max_length=15, choices=Frequency.choices, default=Frequency.DAILY)
    custom_days = models.JSONField(null=True, blank=True)
    mode = models.CharField(max_length=12, choices=Mode.choices, default=Mode.TIME)
    target_volume_mm = models.FloatField(null=True, blank=True)
    target_volume_m3 = models.FloatField(null=True, blank=True)
    priority = models.IntegerField(default=5)
    created_by = models.CharField(max_length=10, choices=CreatedBy.choices, default=CreatedBy.MANUAL)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("programme d'irrigation")
        verbose_name_plural = _("programmes d'irrigation")
        ordering = ("start_hour", "start_minute")

    def __str__(self):
        return self.name


class IrrigationSession(models.Model):
    class TriggeredBy(models.TextChoices):
        MANUAL = "manual", _("Manuel")
        AUTO = "auto", _("Auto")
        IOT = "iot", _("IoT")
        AI = "ai", _("IA")

    exploitation = models.ForeignKey("exploitations.Exploitation", related_name="irrigation_sessions", **EXPLOITATION_FK)
    parcelle = models.ForeignKey("parcelles.Parcelle", related_name="irrigation_sessions", on_delete=models.SET_NULL, null=True, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    volume_delivered_m3 = models.FloatField(null=True, blank=True)
    flow_rate_m3h = models.FloatField(null=True, blank=True)
    pressure_bar = models.FloatField(null=True, blank=True)
    energy_kwh = models.FloatField(null=True, blank=True)
    kwh_per_m3 = models.FloatField(null=True, blank=True)
    triggered_by = models.CharField(max_length=10, choices=TriggeredBy.choices, default=TriggeredBy.MANUAL)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("session d'irrigation")
        verbose_name_plural = _("sessions d'irrigation")
        ordering = ("-start_time",)


class PumpingStation(TimeStampedModel):
    class Status(models.TextChoices):
        OPERATIONAL = "operational", _("Opérationnelle")
        MAINTENANCE = "maintenance", _("Maintenance")
        BROKEN = "broken", _("En panne")

    exploitation = models.ForeignKey("exploitations.Exploitation", related_name="pumping_stations", **EXPLOITATION_FK)
    name = models.CharField(max_length=255)
    power_kw = models.FloatField(null=True, blank=True)
    max_flow_m3h = models.FloatField(null=True, blank=True)
    max_pressure_bar = models.FloatField(null=True, blank=True)
    efficiency = models.FloatField(default=0.75)
    energy_tariff_kwh = models.FloatField(default=0.15)
    water_tariff_m3 = models.FloatField(default=0)
    has_variable_drive = models.BooleanField(default=False)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPERATIONAL)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("station de pompage")
        verbose_name_plural = _("stations de pompage")

    def __str__(self):
        return self.name


class BassinageEvent(models.Model):
    class TriggeredBy(models.TextChoices):
        MANUAL = "manual", _("Manuel")
        AUTO = "auto", _("Auto")
        SENSOR = "sensor", _("Capteur")

    class Status(models.TextChoices):
        ACTIVE = "active", _("Actif")
        COMPLETED = "completed", _("Terminé")
        CANCELLED = "cancelled", _("Annulé")

    exploitation = models.ForeignKey("exploitations.Exploitation", related_name="bassinage_events", **EXPLOITATION_FK)
    parcelle = models.ForeignKey("parcelles.Parcelle", related_name="bassinage_events", on_delete=models.CASCADE)
    zone = models.ForeignKey(IrrigationZone, on_delete=models.SET_NULL, null=True, blank=True)
    sensor = models.ForeignKey("iot.IotDevice", on_delete=models.SET_NULL, null=True, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.IntegerField(null=True, blank=True)
    trigger_temperature = models.FloatField(null=True, blank=True)
    water_used_m3 = models.FloatField(null=True, blank=True)
    interrupted_program = models.ForeignKey(IrrigationProgram, on_delete=models.SET_NULL, null=True, blank=True)
    auto_resume_irrigation = models.BooleanField(default=True)
    triggered_by = models.CharField(max_length=10, choices=TriggeredBy.choices, default=TriggeredBy.MANUAL)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("événement de bassinage")
        verbose_name_plural = _("événements de bassinage")
        ordering = ("-start_time",)


# ── Eau & énergie ───────────────────────────────────────────────────────────
class WaterMeter(models.Model):
    class Source(models.TextChoices):
        VYRSA = "vyrsa_api", "Vyrsa API"
        MANUAL = "manual", _("Manuel")
        IOT = "iot_webhook", "IoT webhook"

    exploitation = models.ForeignKey("exploitations.Exploitation", related_name="water_meters", **EXPLOITATION_FK)
    device = models.ForeignKey("iot.IotDevice", on_delete=models.SET_NULL, null=True, blank=True)
    parcelle = models.ForeignKey("parcelles.Parcelle", on_delete=models.SET_NULL, null=True, blank=True)
    reading_date = models.DateTimeField()
    volume_m3 = models.FloatField()
    flow_rate_m3h = models.FloatField(null=True, blank=True)
    cumulative_m3 = models.FloatField(null=True, blank=True)
    source = models.CharField(max_length=12, choices=Source.choices, default=Source.VYRSA)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("relevé compteur eau")
        verbose_name_plural = _("relevés compteur eau")
        ordering = ("-reading_date",)
        indexes = [models.Index(fields=["exploitation", "-reading_date"])]


class EnergyLog(models.Model):
    class Source(models.TextChoices):
        SCHNEIDER = "schneider", "Schneider"
        SHELLY = "shelly", "Shelly"
        MANUAL = "manual", _("Manuel")
        IOT = "iot_webhook", "IoT webhook"

    exploitation = models.ForeignKey("exploitations.Exploitation", related_name="energy_logs", **EXPLOITATION_FK)
    device = models.ForeignKey("iot.IotDevice", on_delete=models.SET_NULL, null=True, blank=True)
    parcelle = models.ForeignKey("parcelles.Parcelle", on_delete=models.SET_NULL, null=True, blank=True)
    log_date = models.DateTimeField()
    energy_kwh = models.FloatField()
    power_kw = models.FloatField(null=True, blank=True)
    voltage_v = models.FloatField(null=True, blank=True)
    current_a = models.FloatField(null=True, blank=True)
    power_factor = models.FloatField(null=True, blank=True)
    source = models.CharField(max_length=12, choices=Source.choices, default=Source.MANUAL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("relevé énergie")
        verbose_name_plural = _("relevés énergie")
        ordering = ("-log_date",)
        indexes = [models.Index(fields=["exploitation", "-log_date"])]


class WaterQuota(TimeStampedModel):
    class Period(models.TextChoices):
        ANNUAL = "annual", _("Annuel")
        MONTHLY = "monthly", _("Mensuel")
        WEEKLY = "weekly", _("Hebdomadaire")

    exploitation = models.ForeignKey("exploitations.Exploitation", related_name="water_quotas", **EXPLOITATION_FK)
    year = models.IntegerField()
    total_quota_m3 = models.FloatField()
    used_m3 = models.FloatField(default=0)
    period = models.CharField(max_length=10, choices=Period.choices, default=Period.ANNUAL)
    month = models.IntegerField(null=True, blank=True)
    alert_threshold = models.FloatField(default=0.8)

    class Meta:
        verbose_name = _("quota eau")
        verbose_name_plural = _("quotas eau")
        ordering = ("-year",)


# ── DTI, gel, NDVI, pertes invisibles ───────────────────────────────────────
class DtiScore(models.Model):
    class Score(models.TextChoices):
        A = "A", "A"
        B = "B", "B"
        C = "C", "C"
        D = "D", "D"

    exploitation = models.ForeignKey("exploitations.Exploitation", related_name="dti_scores", **EXPLOITATION_FK)
    parcelle = models.ForeignKey("parcelles.Parcelle", on_delete=models.SET_NULL, null=True, blank=True)
    score = models.CharField(max_length=1, choices=Score.choices)
    score_numeric = models.FloatField()
    kwh_per_m3 = models.FloatField(null=True, blank=True)
    flow_rate_m3h = models.FloatField(null=True, blank=True)
    pressure_bar = models.FloatField(null=True, blank=True)
    etp_mm = models.FloatField(null=True, blank=True)
    uniformity_coeff = models.FloatField(null=True, blank=True)
    recommendations = models.JSONField(null=True, blank=True)
    calculated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("score DTI")
        verbose_name_plural = _("scores DTI")
        ordering = ("-calculated_at",)


class FrostEvent(models.Model):
    class RiskLevel(models.TextChoices):
        LOW = "low", _("Faible")
        MEDIUM = "medium", _("Moyen")
        HIGH = "high", _("Élevé")
        CRITICAL = "critical", _("Critique")

    exploitation = models.ForeignKey("exploitations.Exploitation", related_name="frost_events", **EXPLOITATION_FK)
    parcelle = models.ForeignKey("parcelles.Parcelle", on_delete=models.SET_NULL, null=True, blank=True)
    detected_at = models.DateTimeField()
    temperature_c = models.FloatField()
    threshold_c = models.FloatField()
    risk_level = models.CharField(max_length=10, choices=RiskLevel.choices, default=RiskLevel.MEDIUM)
    bassinage = models.BooleanField(default=False)
    bassinage_start_at = models.DateTimeField(null=True, blank=True)
    bassinage_end_at = models.DateTimeField(null=True, blank=True)
    volume_bassinage_m3 = models.FloatField(null=True, blank=True)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("événement de gel")
        verbose_name_plural = _("événements de gel")
        ordering = ("-detected_at",)


class NdviData(models.Model):
    exploitation = models.ForeignKey("exploitations.Exploitation", related_name="ndvi_data", **EXPLOITATION_FK)
    parcelle = models.ForeignKey("parcelles.Parcelle", related_name="ndvi_data", on_delete=models.CASCADE)
    acquisition_date = models.DateTimeField()
    ndvi_min = models.FloatField(null=True, blank=True)
    ndvi_max = models.FloatField(null=True, blank=True)
    ndvi_mean = models.FloatField()
    ndvi_std = models.FloatField(null=True, blank=True)
    cloud_coverage = models.FloatField(null=True, blank=True)
    image_url = models.TextField(blank=True)
    source = models.CharField(max_length=50, default="sentinel2")
    agro_polygon_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("donnée NDVI")
        verbose_name_plural = _("données NDVI")
        ordering = ("-acquisition_date",)


class InvisibleLossDetection(models.Model):
    exploitation = models.ForeignKey("exploitations.Exploitation", related_name="invisible_losses", **EXPLOITATION_FK)
    parcelle = models.ForeignKey("parcelles.Parcelle", related_name="invisible_losses", on_delete=models.CASCADE)
    detected_at = models.DateTimeField()
    theoretical_flow_m3h = models.FloatField()
    actual_flow_m3h = models.FloatField()
    deviation_pct = models.FloatField()
    estimated_loss_m3h = models.FloatField(null=True, blank=True)
    alert_triggered = models.BooleanField(default=False)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("détection de perte invisible")
        verbose_name_plural = _("détections de pertes invisibles")
        ordering = ("-detected_at",)
