from datetime import timedelta

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

#: Heure d'ancrage par défaut. Avec la fréquence par défaut (12 h), les captures
#: tombent à 06:00 et 18:00 — le matin avant la journée de travail, le soir après.
CAPTURE_HEURE_DEFAUT = 6


def heures_de_capture(frequence, heure_debut):
    """Les heures rondes de déclenchement dans une journée, en heure locale.

    Les créneaux sont **ancrés sur l'horloge**, pas sur la dernière capture :
    12 h à partir de 6 → [6, 18], quel que soit le moment où la case a été
    cochée. Sans ancrage, un simple « 12 h écoulées » dériverait d'un peu à
    chaque tour de cron et finirait par capturer en pleine nuit.
    """
    frequence = max(1, min(24, int(frequence)))
    return list(range(int(heure_debut) % frequence, 24, frequence))


def dernier_creneau(frequence, heure_debut, maintenant=None):
    """Le dernier créneau échu (aware, heure locale) à l'instant `maintenant`."""
    local = timezone.localtime(maintenant or timezone.now())
    heures = heures_de_capture(frequence, heure_debut)
    passees = [h for h in heures if h <= local.hour]
    if passees:
        return local.replace(hour=passees[-1], minute=0, second=0, microsecond=0)
    # Aucun créneau atteint aujourd'hui : le dernier est le dernier d'hier.
    return (local - timedelta(days=1)).replace(
        hour=heures[-1], minute=0, second=0, microsecond=0
    )


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
    capture_auto = models.BooleanField(_("capture automatique"), default=True)
    capture_frequence = models.PositiveIntegerField(
        _("fréquence"), choices=Frequence.choices, default=Frequence.DOUZE_H
    )
    capture_heure_debut = models.PositiveSmallIntegerField(
        _("première capture de la journée"), default=CAPTURE_HEURE_DEFAUT,
        help_text=_("Heure d'ancrage des créneaux (0–23)."),
    )
    capture_last_run = models.DateTimeField(_("dernière capture auto"), null=True, blank=True)

    class Meta:
        verbose_name = _("ville météo")
        verbose_name_plural = _("villes météo")
        ordering = ("nom",)
        unique_together = ("exploitation", "slug")

    def __str__(self):
        return self.nom

    @property
    def heures_capture(self):
        """Les heures de capture de cette ville — p. ex. [6, 18]."""
        return heures_de_capture(self.capture_frequence, self.capture_heure_debut)

    def capture_due(self, maintenant=None):
        """Le créneau courant est-il encore à capturer ?

        Vrai tant que la dernière capture est antérieure au dernier créneau
        échu : le cron peut donc tourner à n'importe quelle cadence (et repasser
        après une panne) sans jamais dupliquer ni sauter un créneau.
        """
        if self.capture_last_run is None:
            return True
        return self.capture_last_run < dernier_creneau(
            self.capture_frequence, self.capture_heure_debut, maintenant
        )


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
