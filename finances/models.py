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
    #: Le logo qui s'imprime en tête. Vide → celui marqué par défaut, de
    #: sorte qu'un document ancien suit la marque courante.
    logo = models.ForeignKey(
        "finances.Logo", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="%(class)ss", verbose_name=_("logo"))
    notes = models.TextField(blank=True)

    # ── Acceptation par le client ──────────────────────────────────────
    #: Un devis n'engage qu'une fois signé de la main du client, sous la
    #: mention manuscrite « Bon pour accord » (art. 1583 du code civil : la
    #: vente est parfaite dès l'accord sur la chose et le prix). Tant que ces
    #: trois éléments manquent, on ne facture pas.
    signature_url = models.TextField(_("signature"), blank=True)
    signature_nom = models.CharField(_("nom du signataire"), max_length=255, blank=True)
    signature_mention = models.CharField(_("mention"), max_length=100, blank=True)
    signature_date = models.DateTimeField(_("signé le"), null=True, blank=True)

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
            and not self.signature_date
            and self.statut in (self.Statut.BROUILLON, self.Statut.ENVOYE)
        )

    @property
    def est_signe(self) -> bool:
        """Signature, nom et mention réunis : le client s'est engagé."""
        return bool(self.signature_url and self.signature_nom and self.signature_mention)

    @property
    def convertible(self) -> bool:
        """Seul un devis signé et pas encore facturé devient une facture."""
        return self.est_signe and not hasattr(self, "facture")


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
    #: Le logo qui s'imprime en tête. Vide → celui marqué par défaut, de
    #: sorte qu'un document ancien suit la marque courante.
    logo = models.ForeignKey(
        "finances.Logo", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="%(class)ss", verbose_name=_("logo"))
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


class Logo(models.Model):
    """Un logo de l'exploitation, réutilisable sur ses documents.

    Une bibliothèque plutôt qu'un champ unique : une exploitation porte
    souvent plusieurs marques — la ferme, la boutique, un label — et le logo
    d'une facture n'est pas toujours celui d'un devis. Ils vivent donc ici,
    et les documents viennent y choisir.

    L'un d'eux est marqué par défaut : c'est celui qu'un nouveau document
    prend sans qu'on ait à le demander.
    """

    #: On s'en tient à ce qui s'ouvre partout et n'alourdit pas un PDF.
    EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
    TAILLE_MAX = 2 * 1024 * 1024

    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE, related_name="logos")
    nom = models.CharField(_("nom"), max_length=120, blank=True)
    fichier = models.ImageField(_("image"), upload_to="logos/%Y/%m/")
    par_defaut = models.BooleanField(
        _("logo par défaut"), default=False,
        help_text=_("Celui que prend un nouveau document, sauf choix contraire."))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("logo")
        verbose_name_plural = _("logos")
        ordering = ("-par_defaut", "nom", "-created_at")
        indexes = [models.Index(fields=["exploitation", "par_defaut"])]

    def __str__(self):
        return self.nom or self.fichier.name

    def save(self, *args, **kwargs):
        # Le nom n'est pas obligatoire : à défaut, celui du fichier fait
        # l'affaire — mieux qu'une ligne vide dans la bibliothèque.
        if not self.nom and self.fichier:
            import os

            self.nom = os.path.splitext(os.path.basename(self.fichier.name))[0][:120]
        super().save(*args, **kwargs)
        if self.par_defaut:
            # Un seul par défaut : le nouveau chasse l'ancien.
            Logo.objects.filter(exploitation=self.exploitation, par_defaut=True).exclude(
                pk=self.pk).update(par_defaut=False)


class IdentiteFacturation(models.Model):
    """Ce qu'une facture doit porter et que l'exploitation ne dit pas ailleurs.

    La raison sociale, le SIRET et la TVA vivent dans `EntrepriseLiee` ;
    l'adresse dans `AdresseExploitation`. On ne les recopie pas ici : une
    identité saisie deux fois finit par se contredire, et sur un document à
    valeur légale c'est un vrai problème.

    Ne restent donc que les mentions propres à la facturation — comment se
    faire payer, et ce que la loi impose d'écrire en pied de document.
    """

    exploitation = models.OneToOneField(
        "exploitations.Exploitation", on_delete=models.CASCADE,
        related_name="identite_facturation")

    # ── Se faire payer ───────────────────────────────────────────────
    banque = models.CharField(_("banque"), max_length=120, blank=True)
    iban = models.CharField(_("IBAN"), max_length=34, blank=True)
    bic = models.CharField(_("BIC"), max_length=11, blank=True)
    conditions_reglement = models.CharField(
        _("conditions de règlement"), max_length=160, blank=True,
        help_text=_("ex : 30 jours fin de mois."))

    # ── Ce que la loi impose ─────────────────────────────────────────
    capital_social = models.FloatField(_("capital social (€)"), null=True, blank=True)
    rcs = models.CharField(
        _("RCS / RM"), max_length=120, blank=True,
        help_text=_("ex : RCS Digne-les-Bains 123 456 789."))
    #: Pénalités de retard et indemnité forfaitaire sont obligatoires sur une
    #: facture entre professionnels : le texte par défaut reprend le minimum
    #: légal, à ajuster selon les conditions de vente.
    mentions = models.TextField(
        _("mentions de pied de page"), blank=True,
        help_text=_("Pénalités de retard, indemnité forfaitaire de recouvrement…"))

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("identité de facturation")
        verbose_name_plural = _("identités de facturation")

    def __str__(self):
        return str(self.exploitation)

    @property
    def iban_lisible(self) -> str:
        """L'IBAN par groupes de quatre : c'est ainsi qu'on le recopie."""
        brut = (self.iban or "").replace(" ", "").upper()
        return " ".join(brut[i:i + 4] for i in range(0, len(brut), 4))

    @property
    def peut_encaisser(self) -> bool:
        """Un IBAN sans BIC suffit en zone SEPA ; sans IBAN, rien à imprimer."""
        return bool(self.iban)


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
