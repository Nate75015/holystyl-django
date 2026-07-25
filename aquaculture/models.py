from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


class Bassin(models.Model):
    """Une installation aquacole : étang, bassin, cage, raceway, table…"""

    class TypeBassin(models.TextChoices):
        ETANG = "etang", _("Étang")
        BASSIN = "bassin", _("Bassin")
        RACEWAY = "raceway", _("Raceway / canal")
        CAGE = "cage", _("Cage flottante")
        RAS = "ras", _("Circuit fermé (RAS)")
        MARAIS = "marais", _("Marais")
        TABLE = "table", _("Table ostréicole")
        FILIERE = "filiere", _("Filière / corde")
        AUTRE = "autre", _("Autre")

    class SourceEau(models.TextChoices):
        FORAGE = "forage", _("Forage")
        RIVIERE = "riviere", _("Rivière")
        SOURCE = "source", _("Source")
        MER = "mer", _("Mer")
        RESEAU = "reseau", _("Réseau")
        PLUVIAL = "pluvial", _("Pluvial")
        AUTRE = "autre", _("Autre")

    class Statut(models.TextChoices):
        EN_SERVICE = "en_service", _("En service")
        ASSEC = "assec", _("En assec")
        MAINTENANCE = "maintenance", _("En maintenance")
        HORS_SERVICE = "hors_service", _("Hors service")

    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE, related_name="bassins"
    )
    nom = models.CharField(_("nom"), max_length=255)
    type_bassin = models.CharField(
        _("type d'installation"), max_length=15, choices=TypeBassin.choices, default=TypeBassin.BASSIN
    )
    statut = models.CharField(
        _("statut"), max_length=15, choices=Statut.choices, default=Statut.EN_SERVICE
    )
    source_eau = models.CharField(
        _("source d'eau"), max_length=15, choices=SourceEau.choices, blank=True
    )
    surface_m2 = models.FloatField(_("surface (m²)"), null=True, blank=True)
    volume_m3 = models.FloatField(_("volume (m³)"), null=True, blank=True)
    profondeur_m = models.FloatField(_("profondeur moyenne (m)"), null=True, blank=True)
    temperature_cible_c = models.FloatField(_("température cible (°C)"), null=True, blank=True)
    notes = models.TextField(_("notes"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("installation aquacole")
        verbose_name_plural = _("installations aquacoles")
        ordering = ("nom",)
        indexes = [models.Index(fields=["exploitation", "statut"])]

    def __str__(self):
        return self.nom

    @property
    def lots_en_elevage(self):
        return self.lots.filter(statut=Lot.Statut.EN_ELEVAGE)

    @property
    def biomasse_kg(self):
        """Biomasse des lots encore en élevage, en kg."""
        return round(sum(lot.biomasse_kg for lot in self.lots_en_elevage), 1)

    @property
    def densite_kg_m3(self):
        """Densité d'élevage — indicateur clé du bien-être et de l'oxygénation."""
        if not self.volume_m3:
            return None
        return round(self.biomasse_kg / self.volume_m3, 2)


class Lot(models.Model):
    """Un lot de poissons ou de coquillages élevé dans une installation."""

    class Statut(models.TextChoices):
        EN_ELEVAGE = "en_elevage", _("En élevage")
        RECOLTE = "recolte", _("Récolté")
        PERDU = "perdu", _("Perte")

    bassin = models.ForeignKey(Bassin, on_delete=models.CASCADE, related_name="lots")
    espece = models.CharField(_("espèce"), max_length=255)
    souche = models.CharField(_("souche / origine"), max_length=255, blank=True)
    effectif = models.PositiveIntegerField(_("effectif"), null=True, blank=True)
    poids_moyen_g = models.FloatField(_("poids moyen (g)"), null=True, blank=True)
    date_mise_en_charge = models.DateField(_("mise en charge"), null=True, blank=True)
    statut = models.CharField(
        _("statut"), max_length=12, choices=Statut.choices, default=Statut.EN_ELEVAGE
    )
    notes = models.TextField(_("notes"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("lot aquacole")
        verbose_name_plural = _("lots aquacoles")
        ordering = ("-date_mise_en_charge", "espece")
        indexes = [models.Index(fields=["bassin", "statut"])]

    def __str__(self):
        return f"{self.espece} — {self.bassin.nom}"

    @property
    def biomasse_kg(self):
        if not (self.effectif and self.poids_moyen_g):
            return 0.0
        return self.effectif * self.poids_moyen_g / 1000


# ── Référentiel espèces & souches (partagé, comme le référentiel Élevage) ──

class EspeceAquacole(TimeStampedModel):
    """Espèce aquacole rattachée à une grande famille ; porte ses souches."""

    class Famille(models.TextChoices):
        POISSON_EAU_DOUCE = "poisson_eau_douce", _("Poissons d'eau douce")
        POISSON_MARIN = "poisson_marin", _("Poissons marins")
        DIADROME = "diadrome", _("Poissons migrateurs")
        COQUILLAGES = "coquillages", _("Coquillages")
        CRUSTACES = "crustaces", _("Crustacés")
        ALGUES = "algues", _("Algues")
        AUTRE = "autre", _("Autre")

    class Milieu(models.TextChoices):
        DOUCE = "douce", _("Eau douce")
        SAUMATRE = "saumatre", _("Eau saumâtre")
        MARINE = "marine", _("Eau de mer")

    class Production(models.TextChoices):
        CHAIR = "chair", _("Chair")
        CAVIAR = "caviar", _("Œufs / caviar")
        NAISSAIN = "naissain", _("Naissain")
        ALEVINS = "alevins", _("Alevins")
        REPEUPLEMENT = "repeuplement", _("Repeuplement")
        ORNEMENT = "ornement", _("Ornement")
        ALGUES = "algues", _("Algues")
        AUTRE = "autre", _("Autre")

    nom = models.CharField(_("nom"), max_length=255)
    nom_scientifique = models.CharField(_("nom scientifique"), max_length=255, blank=True)
    famille = models.CharField(
        _("famille"), max_length=20, choices=Famille.choices, default=Famille.AUTRE
    )
    milieu = models.CharField(
        _("milieu"), max_length=10, choices=Milieu.choices, default=Milieu.DOUCE
    )
    production = models.CharField(
        _("production"), max_length=15, choices=Production.choices, default=Production.CHAIR
    )
    duree_cycle_jours = models.PositiveIntegerField(
        _("durée du cycle d'élevage (jours)"), null=True, blank=True
    )
    temperature_optimale_c = models.FloatField(_("température optimale (°C)"), null=True, blank=True)
    notes = models.TextField(_("notes"), blank=True)

    class Meta:
        verbose_name = _("espèce aquacole")
        verbose_name_plural = _("espèces aquacoles")
        ordering = ("nom",)

    def __str__(self):
        return self.nom


class Souche(TimeStampedModel):
    """Fiche souche détaillée rattachée à une espèce (lignée, variété d'élevage)."""

    espece = models.ForeignKey(EspeceAquacole, on_delete=models.CASCADE, related_name="souches")
    nom = models.CharField(_("souche"), max_length=255)
    nom_scientifique = models.CharField(_("nom scientifique"), max_length=255, blank=True)
    photo = models.ImageField(_("photo"), upload_to="aquaculture/", null=True, blank=True)
    description = models.TextField(_("description"), blank=True)
    note = models.FloatField(_("note (/5)"), null=True, blank=True)
    nb_avis = models.PositiveIntegerField(_("nombre d'avis"), default=0)

    # Caractéristiques
    livree = models.CharField(_("livrée / couleur"), max_length=255, blank=True)
    poids_adulte = models.CharField(_("poids adulte"), max_length=100, blank=True)
    taille = models.CharField(_("taille"), max_length=100, blank=True)
    aptitude = models.CharField(_("aptitude"), max_length=255, blank=True)
    croissance = models.CharField(_("croissance"), max_length=100, blank=True)
    rusticite = models.CharField(_("rusticité"), max_length=100, blank=True)
    alimentation = models.CharField(_("alimentation"), max_length=255, blank=True)
    particularites = models.CharField(_("particularités"), max_length=255, blank=True)

    # Conseils
    conseil_elevage = models.TextField(_("conseil d'élevage"), blank=True)

    # Origine
    origine = models.CharField(_("origine"), max_length=255, blank=True)
    origine_texte = models.TextField(_("origine (historique)"), blank=True)

    class Meta:
        verbose_name = _("souche")
        verbose_name_plural = _("souches")
        ordering = ("nom",)
        indexes = [models.Index(fields=["espece"])]

    def __str__(self):
        return self.nom
