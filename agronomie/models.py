"""Référentiels agronomiques : coefficients Kc par culture, types de sol, saisons.

Fidèle aux tables Drizzle `cultures_kc`, `types_sol`, `saisons`.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


class CultureKc(TimeStampedModel):
    """Coefficients culturaux (FAO-56) par culture et stade."""

    class Categorie(models.TextChoices):
        CEREALES = "cereales", _("Céréales")
        LEGUMES = "legumes", _("Légumes")
        FRUITS = "fruits", _("Fruits")
        VIGNE = "vigne", _("Vigne")
        OLEAGINEUX = "oleagineux", _("Oléagineux")
        FOURRAGE = "fourrage", _("Fourrage")
        MARAICHAGE = "maraichage", _("Maraîchage")
        AUTRE = "autre", _("Autre")

    nom = models.CharField(_("nom"), max_length=255)
    nom_scientifique = models.CharField(_("nom scientifique"), max_length=255, blank=True)
    categorie = models.CharField(max_length=20, choices=Categorie.choices, default=Categorie.AUTRE)
    kc_initial = models.FloatField(default=0.3)
    kc_mid = models.FloatField(default=1.0)
    kc_end = models.FloatField(default=0.6)
    duration_initial = models.IntegerField(default=30)
    duration_dev = models.IntegerField(default=40)
    duration_mid = models.IntegerField(default=50)
    duration_end = models.IntegerField(default=30)
    source = models.CharField(max_length=100, default="FAO-56")
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("culture (Kc)")
        verbose_name_plural = _("cultures (Kc)")
        ordering = ("nom",)

    def __str__(self):
        return self.nom


class TypeSol(TimeStampedModel):
    """Types de sol et caractéristiques hydriques."""

    class Texture(models.TextChoices):
        SABLEUX = "sableux", _("Sableux")
        LIMONEUX = "limoneux", _("Limoneux")
        ARGILEUX = "argileux", _("Argileux")
        LIMON_ARGILEUX = "limon_argileux", _("Limon argileux")
        SABLO_LIMONEUX = "sablo_limoneux", _("Sablo-limoneux")
        ARGILO_LIMONEUX = "argilo_limoneux", _("Argilo-limoneux")

    nom = models.CharField(_("nom"), max_length=255)
    texture = models.CharField(max_length=20, choices=Texture.choices, default=Texture.LIMONEUX)
    capacite_retention_mm = models.FloatField(_("capacité de rétention (mm)"), default=100)
    ph_typique = models.FloatField(_("pH typique"), default=7.0)
    conductivite_hydraulique = models.FloatField(null=True, blank=True)
    densite_apparente = models.FloatField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("type de sol")
        verbose_name_plural = _("types de sol")
        ordering = ("nom",)

    def __str__(self):
        return self.nom


class Fertigation(models.Model):
    """Apport d'engrais via irrigation (table `fertigations`)."""

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="fertigations")
    parcelle = models.ForeignKey("parcelles.Parcelle", on_delete=models.CASCADE, related_name="fertigations")
    date = models.DateTimeField()
    produit = models.CharField(max_length=255, blank=True)
    azote_n = models.FloatField(default=0)
    phosphore_p = models.FloatField(default=0)
    potassium_k = models.FloatField(default=0)
    volume_l = models.FloatField(default=0)
    concentration = models.FloatField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("fertigation")
        verbose_name_plural = _("fertigations")
        ordering = ("-date",)


class Saison(TimeStampedModel):
    """Saison agronomique d'une exploitation."""

    exploitation = models.ForeignKey(
        "exploitations.Exploitation",
        on_delete=models.CASCADE,
        related_name="saisons",
    )
    nom = models.CharField(_("nom"), max_length=100)
    date_debut = models.DateField(_("date de début"))
    date_fin = models.DateField(_("date de fin"))
    active = models.BooleanField(_("active"), default=False)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("saison")
        verbose_name_plural = _("saisons")
        ordering = ("-date_debut",)

    def __str__(self):
        return self.nom
