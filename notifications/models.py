"""Centre de notifications et règles d'alerte.

Fidèle aux tables Drizzle `notifications`, `notification_rules`.
Le canal (push/email/sms/whatsapp) est stocké dans `channels` (JSON).
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Notification(models.Model):
    class Priority(models.TextChoices):
        BASSE = "basse", _("Basse")
        NORMALE = "normale", _("Normale")
        HAUTE = "haute", _("Haute")
        URGENTE = "urgente", _("Urgente")

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=50)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMALE)
    title = models.CharField(max_length=255)
    message = models.TextField()
    read = models.BooleanField(default=False)
    action_url = models.CharField(max_length=500, blank=True)
    parcelle = models.ForeignKey("parcelles.Parcelle", on_delete=models.SET_NULL, null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("notification")
        verbose_name_plural = _("notifications")
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["user", "-created_at"])]


class NotificationRule(models.Model):
    # `type` et `condition_type` restent des colonnes libres (parité Drizzle, et l'API
    # accepte des valeurs arbitraires). Ces énumérations ne sont donc pas câblées sur les
    # champs : elles cadrent le formulaire web et servent à l'affichage.
    class Type(models.TextChoices):
        IRRIGATION = "irrigation", _("Irrigation")
        METEO = "meteo", _("Météo")
        SOL = "sol", _("Sol")
        CAPTEUR = "capteur", _("Capteur")
        INTERVENTION = "intervention", _("Intervention")

    class ConditionType(models.TextChoices):
        SEUIL_DEPASSE = "seuil_depasse", _("Seuil dépassé")
        SEUIL_SOUS = "seuil_sous", _("Seuil non atteint")
        CHANGEMENT_ETAT = "changement_etat", _("Changement d'état")

    class Metric(models.TextChoices):
        """Grandeurs relevées en temps réel par `meteo.services.fetch_weather`.

        L'ET0 en est absente à dessein : elle n'existe qu'en valeur journalière et
        n'a pas de sens dans une évaluation horaire.
        """

        TEMPERATURE = "temperature", _("Température")
        RESSENTI = "ressenti", _("Température ressentie")
        HUMIDITE = "humidite", _("Humidité")
        VENT = "vent", _("Vent")
        PLUIE = "pluie", _("Pluie")

    #: Conditions qui exigent une valeur de `threshold`.
    THRESHOLD_CONDITIONS = (ConditionType.SEUIL_DEPASSE, ConditionType.SEUIL_SOUS)

    #: Clé de `fetch_weather()["current"]` et unité affichée, par grandeur.
    METRIC_SOURCE = {
        Metric.TEMPERATURE: ("temp", "°C"),
        Metric.RESSENTI: ("ressenti", "°C"),
        Metric.HUMIDITE: ("humidite", "%"),
        Metric.VENT: ("vent", "km/h"),
        Metric.PLUIE: ("pluie", "mm"),
    }

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_rules")
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=50)
    condition_type = models.CharField(max_length=50)
    # Grandeur surveillée. Colonne ajoutée (absente de Drizzle) : sans elle une règle
    # « météo, seuil dépassé, 30 » ne dit pas 30 *quoi*, et reste inévaluable.
    metric = models.CharField(
        max_length=50, choices=Metric.choices, blank=True, verbose_name=_("grandeur")
    )
    threshold = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    # Lieu surveillé, choisi parmi les villes enregistrées sur /meteo/ : requis pour une
    # règle de type « météo », vide pour les autres types.
    ville = models.ForeignKey(
        "meteo.VilleMeteo", on_delete=models.CASCADE, null=True, blank=True,
        related_name="notification_rules", verbose_name=_("lieu"),
    )
    enabled = models.BooleanField(default=True)
    # Alerte au franchissement uniquement : mémorise si le seuil était déjà dépassé au
    # passage précédent, pour ne pas re-notifier à chaque évaluation horaire.
    is_breaching = models.BooleanField(default=False, verbose_name=_("seuil déjà dépassé"))
    channels = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("règle de notification")
        verbose_name_plural = _("règles de notification")
        ordering = ("name",)

    @property
    def metric_unit(self):
        """Unité affichée à côté du seuil (« °C », « % »…), vide si pas de grandeur."""
        source = self.METRIC_SOURCE.get(self.metric)
        return source[1] if source else ""

    @property
    def type_label(self):
        return self.Type(self.type).label if self.type in self.Type.values else self.type

    @property
    def condition_label(self):
        return self.ConditionType(self.condition_type).label if self.condition_type in self.ConditionType.values else self.condition_type
