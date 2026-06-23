"""Couche IoT : devices, télémétrie, commandes, alertes, seuils.

Fidèle aux tables Drizzle `iot_devices`, `iot_telemetry`, `iot_commands`,
`iot_alerts`, `thresholds` (cf. MIGRATION_PLAN §4).
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


class IotDevice(TimeStampedModel):
    class DeviceType(models.TextChoices):
        FLOW_METER = "flow_meter", _("Débitmètre")
        PRESSURE = "pressure_sensor", _("Capteur de pression")
        WEATHER = "weather_station", _("Station météo")
        VALVE = "valve_controller", _("Contrôleur de vanne")
        PUMP = "pump_controller", _("Contrôleur de pompe")
        SOIL_MOISTURE = "soil_moisture", _("Humidité du sol")
        ENERGY = "energy_meter", _("Compteur d'énergie")
        GENERIC = "generic", _("Générique")

    class Brand(models.TextChoices):
        VYRSA = "vyrsa", "Vyrsa"
        SENTEK = "sentek", "Sentek"
        IRRIMETER = "irrimeter", "Irrimeter"
        SCHNEIDER = "schneider", "Schneider"
        GENERIC = "generic", _("Générique")

    class Status(models.TextChoices):
        ONLINE = "online", _("En ligne")
        OFFLINE = "offline", _("Hors ligne")
        WARNING = "warning", _("Avertissement")
        ERROR = "error", _("Erreur")

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="devices")
    parcelle = models.ForeignKey("parcelles.Parcelle", on_delete=models.SET_NULL, null=True, blank=True, related_name="devices")
    name = models.CharField(_("nom"), max_length=255)
    device_type = models.CharField(max_length=20, choices=DeviceType.choices)
    brand = models.CharField(max_length=20, choices=Brand.choices, default=Brand.VYRSA)
    model = models.CharField(max_length=100, blank=True)
    device_id = models.CharField(_("identifiant device"), max_length=100, unique=True)
    serial_number = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_token = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OFFLINE)
    config = models.JSONField(null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    firmware_version = models.CharField(max_length=50, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = _("device IoT")
        verbose_name_plural = _("devices IoT")
        ordering = ("name",)

    def __str__(self):
        return f"{self.name} ({self.device_id})"


class IotTelemetry(models.Model):
    """Mesures capteurs (table volumineuse, PK BigInt)."""

    id = models.BigAutoField(primary_key=True)
    device = models.ForeignKey(IotDevice, on_delete=models.CASCADE, related_name="telemetry")
    timestamp = models.DateTimeField(default=None, null=True, db_index=True)
    payload = models.JSONField(null=True, blank=True)
    primary_value = models.FloatField(null=True, blank=True)
    primary_unit = models.CharField(max_length=50, blank=True)
    flow_rate_m3h = models.FloatField(null=True, blank=True)
    pressure_bar = models.FloatField(null=True, blank=True)
    power_kw = models.FloatField(null=True, blank=True)
    energy_kwh = models.FloatField(null=True, blank=True)
    soil_moisture = models.FloatField(null=True, blank=True)
    signal_strength = models.IntegerField(null=True, blank=True)
    battery_level = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name = _("télémétrie")
        verbose_name_plural = _("télémétries")
        ordering = ("-timestamp",)
        indexes = [models.Index(fields=["device", "-timestamp"])]


class IotCommand(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", _("En attente")
        SENT = "sent", _("Envoyée")
        ACKNOWLEDGED = "acknowledged", _("Accusée")
        COMPLETED = "completed", _("Terminée")
        FAILED = "failed", _("Échouée")
        EXPIRED = "expired", _("Expirée")

    device = models.ForeignKey(IotDevice, on_delete=models.CASCADE, related_name="commands")
    command_type = models.CharField(max_length=100)
    parameters = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    sent_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("commande IoT")
        verbose_name_plural = _("commandes IoT")
        ordering = ("-created_at",)


class IotAlert(models.Model):
    class AlertType(models.TextChoices):
        LEAK = "leak_detected", _("Fuite détectée")
        LOW_PRESSURE = "low_pressure", _("Pression basse")
        HIGH_PRESSURE = "high_pressure", _("Pression haute")
        LOW_FLOW = "low_flow", _("Débit bas")
        HIGH_FLOW = "high_flow", _("Débit élevé")
        PUMP_FAILURE = "pump_failure", _("Panne de pompe")
        UNIFORMITY_DROP = "uniformity_drop", _("Baisse d'uniformité")
        ENERGY_SPIKE = "energy_spike", _("Pic d'énergie")
        OFFLINE = "offline", _("Hors ligne")
        THRESHOLD = "threshold_exceeded", _("Seuil dépassé")
        FROST = "frost_risk", _("Risque de gel")
        INVISIBLE_LOSS = "invisible_loss", _("Perte invisible")

    class Severity(models.TextChoices):
        INFO = "info", _("Info")
        WARNING = "warning", _("Avertissement")
        DANGER = "danger", _("Danger")

    device = models.ForeignKey(IotDevice, on_delete=models.CASCADE, related_name="alerts")
    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="alerts")
    alert_type = models.CharField(max_length=20, choices=AlertType.choices)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.WARNING)
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    threshold_value = models.FloatField(null=True, blank=True)
    actual_value = models.FloatField(null=True, blank=True)
    acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("alerte IoT")
        verbose_name_plural = _("alertes IoT")
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["exploitation", "-created_at"])]


class Threshold(TimeStampedModel):
    class ThresholdType(models.TextChoices):
        FROST = "frost_temperature", _("Température gel")
        MIN_PRESSURE = "min_pressure", _("Pression min")
        MAX_PRESSURE = "max_pressure", _("Pression max")
        MIN_FLOW = "min_flow", _("Débit min")
        MAX_FLOW = "max_flow", _("Débit max")
        MAX_KWH_M3 = "max_kwh_m3", _("kWh/m³ max")
        SOIL_MIN = "soil_moisture_min", _("Humidité sol min")
        SOIL_MAX = "soil_moisture_max", _("Humidité sol max")
        INVISIBLE_LOSS = "invisible_loss_pct", _("Perte invisible %")

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="thresholds")
    parcelle = models.ForeignKey("parcelles.Parcelle", on_delete=models.CASCADE, null=True, blank=True)
    device = models.ForeignKey(IotDevice, on_delete=models.CASCADE, null=True, blank=True)
    threshold_type = models.CharField(max_length=20, choices=ThresholdType.choices)
    min_value = models.FloatField(null=True, blank=True)
    max_value = models.FloatField(null=True, blank=True)
    unit = models.CharField(max_length=20, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("seuil")
        verbose_name_plural = _("seuils")
