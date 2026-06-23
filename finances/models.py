"""Finances & conformité : charges, revenus, récoltes, factures, exports subvention.

Fidèle aux tables Drizzle `charges`, `revenus`, `recoltes`, `facture_clients`,
`factures`, `subvention_exports`.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


class Charge(models.Model):
    class Categorie(models.TextChoices):
        SEMENCES = "semences", _("Semences")
        ENGRAIS = "engrais", _("Engrais")
        PHYTO = "phytosanitaires", _("Phytosanitaires")
        EAU = "eau", _("Eau")
        ENERGIE = "energie", _("Énergie")
        MAIN_OEUVRE = "main_oeuvre", _("Main d'œuvre")
        MATERIEL = "materiel", _("Matériel")
        TRANSPORT = "transport", _("Transport")
        ASSURANCE = "assurance", _("Assurance")
        AUTRE = "autre", _("Autre")

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="charges")
    parcelle = models.ForeignKey("parcelles.Parcelle", on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateTimeField()
    categorie = models.CharField(max_length=20, choices=Categorie.choices, default=Categorie.AUTRE)
    montant = models.FloatField()
    description = models.CharField(max_length=500, blank=True)
    fournisseur = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("charge")
        verbose_name_plural = _("charges")
        ordering = ("-date",)


class Revenu(models.Model):
    class Categorie(models.TextChoices):
        VENTE_CEREALES = "vente_cereales", _("Vente céréales")
        VENTE_FRUITS = "vente_fruits", _("Vente fruits")
        VENTE_LEGUMES = "vente_legumes", _("Vente légumes")
        AIDE_PAC = "aide_pac", _("Aide PAC")
        SUBVENTION = "subvention", _("Subvention")
        LOCATION = "location", _("Location")
        PRESTATION = "prestation", _("Prestation")
        AUTRE = "autre", _("Autre")

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="revenus")
    parcelle = models.ForeignKey("parcelles.Parcelle", on_delete=models.SET_NULL, null=True, blank=True)
    saison = models.ForeignKey("agronomie.Saison", on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateTimeField()
    categorie = models.CharField(max_length=20, choices=Categorie.choices, default=Categorie.AUTRE)
    montant = models.FloatField()
    description = models.CharField(max_length=500, blank=True)
    acheteur = models.CharField(max_length=255, blank=True)
    quantite_kg = models.FloatField(null=True, blank=True)
    prix_unitaire = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("revenu")
        verbose_name_plural = _("revenus")
        ordering = ("-date",)


class Recolte(models.Model):
    class Qualite(models.TextChoices):
        EXTRA = "extra", _("Extra")
        CAT1 = "cat1", _("Catégorie 1")
        CAT2 = "cat2", _("Catégorie 2")
        DECLASSE = "declasse", _("Déclassé")

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="recoltes")
    parcelle = models.ForeignKey("parcelles.Parcelle", on_delete=models.CASCADE, related_name="recoltes")
    date = models.DateTimeField()
    quantite_kg = models.FloatField()
    qualite = models.CharField(max_length=10, choices=Qualite.choices, default=Qualite.CAT1)
    prix_unitaire = models.FloatField(default=0)
    cout_main_oeuvre = models.FloatField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("récolte")
        verbose_name_plural = _("récoltes")
        ordering = ("-date",)


class FactureClient(models.Model):
    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="facture_clients")
    nom = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    telephone = models.CharField(max_length=30, blank=True)
    adresse = models.TextField(blank=True)
    ville = models.CharField(max_length=100, blank=True)
    code_postal = models.CharField(max_length=10, blank=True)
    siret = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("client")
        verbose_name_plural = _("clients")
        ordering = ("nom",)

    def __str__(self):
        return self.nom


class Facture(TimeStampedModel):
    class Statut(models.TextChoices):
        BROUILLON = "brouillon", _("Brouillon")
        EN_ATTENTE = "en_attente", _("En attente")
        PAYEE = "payee", _("Payée")
        EN_RETARD = "en_retard", _("En retard")
        ANNULEE = "annulee", _("Annulée")

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="factures")
    numero = models.CharField(max_length=30)
    client = models.ForeignKey(FactureClient, on_delete=models.SET_NULL, null=True, blank=True, related_name="factures")
    client_nom = models.CharField(max_length=255, blank=True)
    date_emission = models.DateTimeField()
    date_echeance = models.DateTimeField(null=True, blank=True)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE)
    lignes = models.JSONField(default=list, blank=True)
    montant_ht = models.FloatField(default=0)
    taux_tva = models.FloatField(default=20)
    montant_tva = models.FloatField(default=0)
    montant_ttc = models.FloatField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("facture")
        verbose_name_plural = _("factures")
        ordering = ("-date_emission",)
        constraints = [
            models.UniqueConstraint(fields=["exploitation", "numero"], name="unique_facture_numero")
        ]

    def __str__(self):
        return self.numero


class SubventionExport(models.Model):
    class ExportType(models.TextChoices):
        TAXONOMIE = "taxonomie_verte", _("Taxonomie Verte EU")
        PLAN_EAU = "plan_eau_2026", _("Plan Eau 2026")
        PAC = "pac", "PAC / France AgriMer"
        FEADER = "feader", "FEADER"

    class Status(models.TextChoices):
        GENERATING = "generating", _("En génération")
        READY = "ready", _("Prêt")
        ERROR = "error", _("Erreur")

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="subvention_exports")
    export_type = models.CharField(max_length=20, choices=ExportType.choices)
    file_url = models.TextField(blank=True)
    file_key = models.TextField(blank=True)
    period = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.GENERATING)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("export subvention")
        verbose_name_plural = _("exports subvention")
        ordering = ("-generated_at",)
