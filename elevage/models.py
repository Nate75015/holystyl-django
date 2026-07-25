"""Élevage — référentiel animaux : familles → espèces → races.

Même logique que le référentiel cultures (`agronomie.CultureKc` / `Variete`) :
une espèce (ex. « Vache ») appartient à une grande famille (Bovins) et porte
des races (ex. « Limousine ») avec leur fiche détaillée.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


class Espece(TimeStampedModel):
    """Espèce animale rattachée à une grande famille ; porte ses races."""

    class Famille(models.TextChoices):
        BOVINS = "bovins", _("Bovins")
        OVINS = "ovins", _("Ovins")
        CAPRINS = "caprins", _("Caprins")
        PORCINS = "porcins", _("Porcins")
        VOLAILLES = "volailles", _("Volailles")
        EQUIDES = "equides", _("Équidés")
        LAPINS = "lapins", _("Lapins")
        ABEILLES = "abeilles", _("Abeilles")
        AUTRE = "autre", _("Autre")

    class Production(models.TextChoices):
        LAIT = "lait", _("Lait")
        VIANDE = "viande", _("Viande")
        OEUFS = "oeufs", _("Œufs")
        MIXTE = "mixte", _("Mixte")
        LAINE = "laine", _("Laine")
        TRAVAIL = "travail", _("Travail")
        MIEL = "miel", _("Miel")
        AUTRE = "autre", _("Autre")

    nom = models.CharField(_("nom"), max_length=255)
    nom_scientifique = models.CharField(_("nom scientifique"), max_length=255, blank=True)
    famille = models.CharField(_("famille"), max_length=20, choices=Famille.choices, default=Famille.AUTRE)
    production = models.CharField(_("production"), max_length=20, choices=Production.choices, default=Production.MIXTE)
    duree_gestation_jours = models.PositiveIntegerField(_("durée de gestation (jours)"), null=True, blank=True)
    notes = models.TextField(_("notes"), blank=True)

    class Meta:
        verbose_name = _("espèce")
        verbose_name_plural = _("espèces")
        ordering = ("nom",)

    def __str__(self):
        return self.nom


class Race(TimeStampedModel):
    """Fiche race détaillée rattachée à une espèce (sous-espèce)."""

    espece = models.ForeignKey(Espece, on_delete=models.CASCADE, related_name="races")
    nom = models.CharField(_("race"), max_length=255)
    nom_scientifique = models.CharField(_("nom scientifique"), max_length=255, blank=True)
    photo = models.ImageField(_("photo"), upload_to="elevage/", null=True, blank=True)
    description = models.TextField(_("description"), blank=True)
    note = models.FloatField(_("note (/5)"), null=True, blank=True)
    nb_avis = models.PositiveIntegerField(_("nombre d'avis"), default=0)

    # Caractéristiques
    robe = models.CharField(_("robe / plumage"), max_length=255, blank=True)
    poids_adulte = models.CharField(_("poids adulte"), max_length=100, blank=True)
    taille = models.CharField(_("taille"), max_length=100, blank=True)
    aptitude = models.CharField(_("aptitude"), max_length=255, blank=True)
    prolificite = models.CharField(_("prolificité"), max_length=100, blank=True)
    rusticite = models.CharField(_("rusticité"), max_length=100, blank=True)
    alimentation = models.CharField(_("alimentation"), max_length=255, blank=True)
    particularites = models.CharField(_("particularités"), max_length=255, blank=True)

    # Conseils
    conseil_elevage = models.TextField(_("conseil d'élevage"), blank=True)

    # Origine
    origine = models.CharField(_("origine"), max_length=255, blank=True)
    origine_texte = models.TextField(_("origine (historique)"), blank=True)

    class Meta:
        verbose_name = _("race")
        verbose_name_plural = _("races")
        ordering = ("nom",)
        indexes = [models.Index(fields=["espece"])]

    def __str__(self):
        return self.nom
