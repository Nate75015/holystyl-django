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
    """Table historique des clients de facturation (reprise Drizzle).

    Remplacée par `client.Client`, qui est le référentiel unique des clients de
    l'exploitation (page /clients/). Conservée le temps que les consommateurs
    de l'API `facture-clients` s'en détachent ; plus rien ne l'écrit.
    """


    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="facture_clients")
    nom = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    telephone = models.CharField(max_length=30, blank=True)
    adresse = models.TextField(blank=True)
    ville = models.CharField(max_length=100, blank=True)
    code_postal = models.CharField(max_length=10, blank=True)
    siret = models.CharField(max_length=20, blank=True)
    #: Adresse de facturation électronique (annuaire), forme « 0225:315143296_68152 ».
    #: Sans elle, impossible de router une facture vers ce client.
    superpdp_adresse = models.CharField(
        _("adresse de facturation électronique"), max_length=100, blank=True,
        help_text=_("Identifiant d'annuaire, par exemple « 0225:315143296_68152 »."),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("client")
        verbose_name_plural = _("clients")
        ordering = ("nom",)

    def __str__(self):
        return self.nom


class Devis(TimeStampedModel):
    """Proposition commerciale, avant facturation.

    Modèle distinct de `Facture` à dessein : un devis n'est pas une facture et
    ne doit jamais partir sur le réseau de facturation électronique. Ses états
    lui sont propres (accepté, refusé, expiré) et sa numérotation aussi. Une
    fois accepté, il se convertit en facture, qui garde le lien vers lui.
    """

    class Statut(models.TextChoices):
        BROUILLON = "brouillon", _("Brouillon")
        ENVOYE = "envoye", _("Envoyé")
        ACCEPTE = "accepte", _("Accepté")
        REFUSE = "refuse", _("Refusé")
        EXPIRE = "expire", _("Expiré")

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="devis")
    numero = models.CharField(max_length=30)
    client_ref = models.ForeignKey("client.Client", on_delete=models.SET_NULL, null=True, blank=True, related_name="devis")
    client_nom = models.CharField(max_length=255, blank=True)
    date_emission = models.DateTimeField()
    #: Au-delà de cette date, le devis n'engage plus (mention obligatoire).
    date_validite = models.DateTimeField(_("valable jusqu’au"), null=True, blank=True)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.BROUILLON)
    lignes = models.JSONField(default=list, blank=True)
    montant_ht = models.FloatField(default=0)
    taux_tva = models.FloatField(default=20)
    montant_tva = models.FloatField(default=0)
    montant_ttc = models.FloatField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("devis")
        verbose_name_plural = _("devis")
        ordering = ("-date_emission",)
        constraints = [
            models.UniqueConstraint(fields=["exploitation", "numero"], name="unique_devis_numero")
        ]

    def __str__(self):
        return self.numero

    @property
    def est_expire(self) -> bool:
        from django.utils import timezone

        return bool(
            self.date_validite
            and self.date_validite < timezone.now()
            and self.statut in (self.Statut.BROUILLON, self.Statut.ENVOYE)
        )

    @property
    def convertible(self) -> bool:
        """Un devis accepté et pas encore facturé peut devenir une facture."""
        return self.statut == self.Statut.ACCEPTE and not hasattr(self, "facture")


class Facture(TimeStampedModel):
    class Statut(models.TextChoices):
        BROUILLON = "brouillon", _("Brouillon")
        EN_ATTENTE = "en_attente", _("En attente")
        PAYEE = "payee", _("Payée")
        EN_RETARD = "en_retard", _("En retard")
        ANNULEE = "annulee", _("Annulée")

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="factures")
    numero = models.CharField(max_length=30)
    client_ref = models.ForeignKey("client.Client", on_delete=models.SET_NULL, null=True, blank=True, related_name="factures")
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
    #: Devis dont cette facture est issue, le cas échéant.
    devis = models.OneToOneField(
        "Devis", on_delete=models.SET_NULL, null=True, blank=True, related_name="facture",
        verbose_name=_("devis d'origine"),
    )

    # ── Transmission par la plateforme agréée (SUPER PDP) ──────────────
    #: Identifiant de la facture chez SUPER PDP, une fois déposée.
    superpdp_id = models.IntegerField(_("identifiant SUPER PDP"), null=True, blank=True)
    #: Dernier code de statut du cycle de vie (fr:204 … fr:220).
    superpdp_statut = models.CharField(_("statut SUPER PDP"), max_length=20, blank=True)
    superpdp_envoye_le = models.DateTimeField(_("envoyée le"), null=True, blank=True)
    #: Message du dernier échec (validation ou dépôt), affiché tel quel.
    superpdp_erreur = models.TextField(_("erreur SUPER PDP"), blank=True)

    @property
    def superpdp_envoyee(self) -> bool:
        return self.superpdp_id is not None

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
