"""Référentiels agronomiques : coefficients Kc par culture, types de sol.

Fidèle aux tables Drizzle `cultures_kc`, `types_sol`.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


def expand_months(start, end):
    """Liste des mois (1–12) couverts par une période, gère le passage d'année."""
    if not start or not end:
        return []
    if start <= end:
        return list(range(start, end + 1))
    return list(range(start, 13)) + list(range(1, end + 1))


class CultureKc(TimeStampedModel):
    """Culture (espèce) : coefficients culturaux FAO-56 + calendrier général.
    Les fiches détaillées (photo, description, caractéristiques…) sont portées
    par ses variétés (modèle `Variete`)."""

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
    # Calendrier : périodes de semis et de récolte (mois 1–12, bornes incluses ;
    # si début > fin, la période chevauche l'hiver, ex. 10→3).
    semis_debut = models.PositiveSmallIntegerField(_("semis — mois de début"), null=True, blank=True)
    semis_fin = models.PositiveSmallIntegerField(_("semis — mois de fin"), null=True, blank=True)
    recolte_debut = models.PositiveSmallIntegerField(_("récolte — mois de début"), null=True, blank=True)
    recolte_fin = models.PositiveSmallIntegerField(_("récolte — mois de fin"), null=True, blank=True)
    source = models.CharField(max_length=100, default="FAO-56")
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("culture (Kc)")
        verbose_name_plural = _("cultures (Kc)")
        ordering = ("nom",)

    def __str__(self):
        return self.nom

    # Rétrocompat : appel statique conservé.
    expand_months = staticmethod(expand_months)

    @property
    def semis_mois(self):
        return expand_months(self.semis_debut, self.semis_fin)

    @property
    def recolte_mois(self):
        return expand_months(self.recolte_debut, self.recolte_fin)


class Variete(TimeStampedModel):
    """Fiche variété détaillée rattachée à une culture (type catalogue de semences)."""

    class Exposition(models.TextChoices):
        PLEIN_SOLEIL = "plein_soleil", _("Plein soleil")
        MI_OMBRE = "mi_ombre", _("Mi-ombre")
        OMBRE = "ombre", _("Ombre")

    class Arrosage(models.TextChoices):
        FAIBLE = "faible", _("Faible")
        MOYEN = "moyen", _("Moyen")
        ELEVE = "eleve", _("Élevé")

    culture = models.ForeignKey(CultureKc, on_delete=models.CASCADE, related_name="varietes")
    nom = models.CharField(_("variété"), max_length=255)
    nom_scientifique = models.CharField(_("nom scientifique"), max_length=255, blank=True)
    photo = models.ImageField(_("photo"), upload_to="cultures/", null=True, blank=True)
    description = models.TextField(_("description"), blank=True)
    note = models.FloatField(_("note (/5)"), null=True, blank=True)
    nb_avis = models.PositiveIntegerField(_("nombre d'avis"), default=0)

    # Calendrier propre à la variété (facultatif ; sinon celui de la culture)
    semis_debut = models.PositiveSmallIntegerField(null=True, blank=True)
    semis_fin = models.PositiveSmallIntegerField(null=True, blank=True)
    recolte_debut = models.PositiveSmallIntegerField(null=True, blank=True)
    recolte_fin = models.PositiveSmallIntegerField(null=True, blank=True)

    # Conditions de culture
    exposition = models.CharField(_("exposition"), max_length=15, choices=Exposition.choices, blank=True)
    arrosage = models.CharField(_("arrosage"), max_length=15, choices=Arrosage.choices, blank=True)
    nature_sol = models.CharField(_("nature du sol"), max_length=255, blank=True)
    sol_detail = models.CharField(_("sol (détail)"), max_length=255, blank=True)
    mode_culture = models.CharField(_("mode de culture"), max_length=255, blank=True)

    # Conseils
    conseil_semis = models.TextField(_("conseil de semis"), blank=True)
    conseil_culture = models.TextField(_("conseil de culture"), blank=True)

    # Caractéristiques
    poids = models.CharField(_("poids"), max_length=100, blank=True)
    contenance_sachet = models.CharField(_("contenance du sachet"), max_length=100, blank=True)
    forme = models.CharField(_("forme"), max_length=100, blank=True)
    texture_fruit = models.CharField(_("texture"), max_length=100, blank=True)
    type_croissance = models.CharField(_("type de croissance"), max_length=100, blank=True)
    couleur = models.CharField(_("couleur"), max_length=100, blank=True)
    feuillage = models.CharField(_("feuillage"), max_length=100, blank=True)
    type_semis = models.CharField(_("semis"), max_length=100, blank=True)

    # Origine
    origine = models.CharField(_("origine"), max_length=255, blank=True)
    origine_texte = models.TextField(_("origine (historique)"), blank=True)
    source = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = _("variété")
        verbose_name_plural = _("variétés")
        ordering = ("nom",)
        indexes = [models.Index(fields=["culture"])]

    def __str__(self):
        return self.nom

    @property
    def semis_mois(self):
        return expand_months(self.semis_debut or self.culture.semis_debut,
                             self.semis_fin or self.culture.semis_fin)

    @property
    def recolte_mois(self):
        return expand_months(self.recolte_debut or self.culture.recolte_debut,
                             self.recolte_fin or self.culture.recolte_fin)


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


class Engrais(TimeStampedModel):
    """Catalogue d'engrais (référentiel) : titres N/P/K, solubilité, effet pH."""

    class Type(models.TextChoices):
        N = "N", "N"
        P = "P", "P"
        K = "K", "K"
        NP = "NP", "NP"
        NK = "NK", "NK"
        NPK = "NPK", "NPK"

    nom = models.CharField(_("nom"), max_length=255)
    type_engrais = models.CharField(_("type"), max_length=4, choices=Type.choices, default=Type.NPK)
    n_pct = models.FloatField(_("N %"), null=True, blank=True)
    p_pct = models.FloatField(_("P %"), null=True, blank=True)
    k_pct = models.FloatField(_("K %"), null=True, blank=True)
    solubilite = models.CharField(_("solubilité"), max_length=50, blank=True)
    ph_effet = models.CharField(_("effet pH"), max_length=50, blank=True)

    class Meta:
        verbose_name = _("engrais")
        verbose_name_plural = _("engrais")
        ordering = ("nom",)

    def __str__(self):
        return self.nom
