from django.db import models
from django.utils.translation import gettext_lazy as _


class VilleMeteo(models.Model):
    """Ville enregistrée (favori) + planning de capture automatique propre à la ville."""

    class Frequence(models.IntegerChoices):
        HORAIRE = 1, _("Toutes les heures")
        SIX_H = 6, _("Toutes les 6 heures")
        DOUZE_H = 12, _("Toutes les 12 heures")
        QUOTIDIEN = 24, _("Quotidienne")

    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE, related_name="villes_meteo"
    )
    nom = models.CharField(_("nom"), max_length=255)
    slug = models.SlugField(_("slug"), max_length=255, blank=True)
    latitude = models.FloatField(_("latitude"))
    longitude = models.FloatField(_("longitude"))
    created_at = models.DateTimeField(auto_now_add=True)

    # Capture automatique (par ville)
    capture_auto = models.BooleanField(_("capture automatique"), default=False)
    capture_frequence = models.PositiveIntegerField(
        _("fréquence"), choices=Frequence.choices, default=Frequence.QUOTIDIEN
    )
    capture_last_run = models.DateTimeField(_("dernière capture auto"), null=True, blank=True)

    class Meta:
        verbose_name = _("ville météo")
        verbose_name_plural = _("villes météo")
        ordering = ("nom",)
        unique_together = ("exploitation", "slug")

    def __str__(self):
        return self.nom


class ReleveMeteo(models.Model):
    """Capture (snapshot) de la météo à un instant donné, pour constituer un historique."""

    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE, related_name="releves_meteo"
    )
    lieu = models.CharField(_("lieu"), max_length=255, blank=True)
    latitude = models.FloatField(_("latitude"))
    longitude = models.FloatField(_("longitude"))
    temperature = models.FloatField(_("température (°C)"), null=True, blank=True)
    humidite = models.FloatField(_("humidité (%)"), null=True, blank=True)
    vent = models.FloatField(_("vent (km/h)"), null=True, blank=True)
    pluie = models.FloatField(_("pluie (mm)"), null=True, blank=True)
    et0 = models.FloatField(_("ET0 (mm)"), null=True, blank=True)
    libelle = models.CharField(_("conditions"), max_length=100, blank=True)
    captured_at = models.DateTimeField(_("capturé le"), auto_now_add=True)

    class Meta:
        verbose_name = _("relevé météo")
        verbose_name_plural = _("relevés météo")
        ordering = ("-captured_at",)

    def __str__(self):
        return f"{self.lieu} {self.captured_at:%d/%m/%Y %H:%M}"
