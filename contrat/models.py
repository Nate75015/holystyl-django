from django.db import models
from django.utils.translation import gettext_lazy as _


class Contrat(models.Model):
    """Un contrat de l'exploitation (bail, prestation, vente, assurance…)."""

    class TypeContrat(models.TextChoices):
        BAIL = "bail", _("Bail rural / fermage")
        PRESTATION = "prestation", _("Prestation de service")
        VENTE = "vente", _("Contrat de vente")
        APPRO = "appro", _("Approvisionnement")
        ASSURANCE = "assurance", _("Assurance")
        SALARIE = "salarie", _("Contrat de travail")
        AUTRE = "autre", _("Autre")

    class Statut(models.TextChoices):
        BROUILLON = "brouillon", _("Brouillon")
        ACTIF = "actif", _("Actif")
        EXPIRE = "expire", _("Expiré")
        RESILIE = "resilie", _("Résilié")

    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE, related_name="contrats"
    )
    intitule = models.CharField(_("intitulé"), max_length=255)
    type_contrat = models.CharField(
        _("type"), max_length=20, choices=TypeContrat.choices, default=TypeContrat.AUTRE
    )
    contractant = models.CharField(_("contractant"), max_length=255, blank=True)
    date_debut = models.DateField(_("date de début"), null=True, blank=True)
    date_fin = models.DateField(_("date de fin"), null=True, blank=True)
    montant = models.FloatField(_("montant (€)"), null=True, blank=True)
    statut = models.CharField(
        _("statut"), max_length=12, choices=Statut.choices, default=Statut.BROUILLON
    )
    notes = models.TextField(_("notes"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("contrat")
        verbose_name_plural = _("contrats")
        ordering = ("-date_debut", "-created_at")
        indexes = [models.Index(fields=["exploitation", "statut"])]

    def __str__(self):
        return self.intitule

class Bail(models.Model):
    """Un bail rural (fermage) : location de terres agricoles."""

    class Statut(models.TextChoices):
        BROUILLON = "brouillon", _("Brouillon")
        ACTIF = "actif", _("Actif")
        EXPIRE = "expire", _("Expiré")
        RESILIE = "resilie", _("Résilié")

    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE, related_name="baux"
    )
    designation = models.CharField(_("désignation"), max_length=255)
    bailleur = models.CharField(_("bailleur"), max_length=255, blank=True)
    # `bailleur` reste le nom en clair (saisie libre, baux historiques). Cette FK
    # est ce qui rattache réellement le bail à une fiche Partenaire, et donc à
    # l'espace bailleur : sans elle, on en serait réduit à comparer des chaînes.
    partenaire = models.ForeignKey(
        "client.Partenaire",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="baux",
        verbose_name=_("fiche bailleur"),
    )
    preneur = models.CharField(_("preneur"), max_length=255, blank=True)
    surface_ha = models.FloatField(_("surface (ha)"), null=True, blank=True)
    loyer_annuel = models.FloatField(_("fermage annuel (€)"), null=True, blank=True)
    # Révision du fermage : loyer de base et son année, puis application des
    # indices nationaux successifs. L'encadrement est fixé par arrêté préfectoral
    # (il varie par département et par nature de culture), donc saisi par bail.
    loyer_base_ha = models.FloatField(_("loyer de base (€/ha)"), null=True, blank=True)
    annee_reference = models.PositiveIntegerField(
        _("année de référence du loyer de base"), null=True, blank=True
    )
    loyer_mini_ha = models.FloatField(_("minimum préfectoral (€/ha)"), null=True, blank=True)
    loyer_maxi_ha = models.FloatField(_("maximum préfectoral (€/ha)"), null=True, blank=True)
    date_debut = models.DateField(_("date de début"), null=True, blank=True)
    date_fin = models.DateField(_("date de fin"), null=True, blank=True)
    statut = models.CharField(
        _("statut"), max_length=12, choices=Statut.choices, default=Statut.BROUILLON
    )
    notes = models.TextField(_("notes"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("bail")
        verbose_name_plural = _("baux")
        ordering = ("-date_debut", "-created_at")
        indexes = [models.Index(fields=["exploitation", "statut"])]

    def __str__(self):
        return self.designation


class ActeNotarie(models.Model):
    """Un acte notarié (vente, achat, servitude, succession…)."""

    class TypeActe(models.TextChoices):
        VENTE = "vente", _("Vente")
        ACHAT = "achat", _("Achat")
        DONATION = "donation", _("Donation")
        SUCCESSION = "succession", _("Succession")
        SERVITUDE = "servitude", _("Servitude")
        HYPOTHEQUE = "hypotheque", _("Hypothèque")
        AUTRE = "autre", _("Autre")

    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE, related_name="actes_notaries"
    )
    objet = models.CharField(_("objet"), max_length=255)
    type_acte = models.CharField(
        _("type d'acte"), max_length=20, choices=TypeActe.choices, default=TypeActe.AUTRE
    )
    notaire = models.CharField(_("notaire / étude"), max_length=255, blank=True)
    parties = models.CharField(_("parties"), max_length=255, blank=True)
    reference = models.CharField(_("référence de l'acte"), max_length=100, blank=True)
    date_signature = models.DateField(_("date de signature"), null=True, blank=True)
    montant = models.FloatField(_("montant (€)"), null=True, blank=True)
    notes = models.TextField(_("notes"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("acte notarié")
        verbose_name_plural = _("actes notariés")
        ordering = ("-date_signature", "-created_at")
        indexes = [models.Index(fields=["exploitation", "type_acte"])]

    def __str__(self):
        return self.objet


class Assurance(models.Model):
    """Un contrat d'assurance de l'exploitation (multirisque, récolte, RC…)."""

    class TypeAssurance(models.TextChoices):
        """Ce qu'une exploitation assure réellement.

        Une ferme porte rarement une police : la multirisque couvre le socle,
        la multirisque climatique les récoltes, et s'y ajoutent les véhicules,
        le matériel, le cheptel, la protection juridique, la prévoyance…
        """

        MULTIRISQUE = "multirisque", _("Multirisque agricole")
        RECOLTE = "recolte", _("Multirisque climatique (récoltes)")
        GRELE = "grele", _("Grêle")
        RC = "rc", _("Responsabilité civile exploitation")
        RC_DIRIGEANT = "rc_dirigeant", _("Responsabilité civile du dirigeant")
        VEHICULES = "vehicules", _("Véhicules et engins")
        MATERIEL = "materiel", _("Matériel et bris de machine")
        BATIMENTS = "batiments", _("Bâtiments")
        BETAIL = "betail", _("Cheptel et mortalité du bétail")
        PERTE_EXPLOITATION = "perte_exploitation", _("Perte d'exploitation")
        PROTECTION_JURIDIQUE = "protection_juridique", _("Protection juridique")
        ENVIRONNEMENT = "environnement", _("Atteinte à l'environnement")
        SANTE_PREVOYANCE = "sante_prevoyance", _("Santé et prévoyance")
        EMPRUNTEUR = "emprunteur", _("Emprunteur")
        CONSTRUCTION = "construction", _("Construction / dommages-ouvrage")
        TRANSPORT = "transport", _("Transport de marchandises")
        CYBER = "cyber", _("Cyber")
        AUTRE = "autre", _("Autre")

    class Statut(models.TextChoices):
        BROUILLON = "brouillon", _("Brouillon")
        ACTIVE = "active", _("Active")
        EXPIREE = "expiree", _("Expirée")
        RESILIEE = "resiliee", _("Résiliée")

    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE, related_name="assurances"
    )
    intitule = models.CharField(_("intitulé"), max_length=255)
    type_assurance = models.CharField(
        _("type"), max_length=20, choices=TypeAssurance.choices, default=TypeAssurance.MULTIRISQUE
    )
    assureur = models.CharField(_("assureur"), max_length=255, blank=True)
    numero_police = models.CharField(_("n° de police"), max_length=100, blank=True)
    prime_annuelle = models.FloatField(_("prime annuelle (€)"), null=True, blank=True)
    capital_assure = models.FloatField(_("capital assuré (€)"), null=True, blank=True)
    date_debut = models.DateField(_("date de début"), null=True, blank=True)
    date_fin = models.DateField(_("échéance"), null=True, blank=True)
    statut = models.CharField(
        _("statut"), max_length=12, choices=Statut.choices, default=Statut.BROUILLON
    )
    date_resiliation = models.DateField(_("résiliée le"), null=True, blank=True)

    # ── Ce qu'il faut savoir pour s'en servir ────────────────────────
    #
    # Un contrat d'assurance ne sert que le jour du sinistre, et ce jour-là on
    # cherche trois choses dans l'urgence : qui appeler, sous quel délai, et ce
    # qui reste à charge. Elles vivent ici plutôt que noyées dans les notes.
    garanties = models.TextField(_("garanties"), blank=True)
    exclusions = models.TextField(_("exclusions"), blank=True)
    franchise = models.CharField(_("franchise"), max_length=255, blank=True)
    plafond = models.FloatField(_("plafond d'indemnisation (€)"), null=True, blank=True)
    delai_declaration_jours = models.PositiveIntegerField(
        _("délai de déclaration (jours)"), null=True, blank=True,
        help_text=_("Cinq jours ouvrés en général, deux pour le vol, dix après un "
                    "arrêté de catastrophe naturelle."))
    procedure_sinistre = models.TextField(_("marche à suivre en cas de sinistre"), blank=True)
    telephone_sinistre = models.CharField(_("téléphone sinistre"), max_length=30, blank=True)
    email_sinistre = models.EmailField(_("email sinistre"), blank=True)

    # ── L'interlocuteur, et comment sortir ───────────────────────────
    courtier = models.CharField(_("courtier ou agence"), max_length=255, blank=True)
    telephone_courtier = models.CharField(_("téléphone du courtier"), max_length=30, blank=True)
    email_courtier = models.EmailField(_("email du courtier"), blank=True)
    tacite_reconduction = models.BooleanField(_("tacite reconduction"), default=True)
    preavis_resiliation_jours = models.PositiveIntegerField(
        _("préavis de résiliation (jours)"), null=True, blank=True,
        help_text=_("Deux mois avant l'échéance dans la plupart des contrats."))

    notes = models.TextField(_("notes"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("assurance")
        verbose_name_plural = _("assurances")
        ordering = ("-date_debut", "-created_at")
        indexes = [models.Index(fields=["exploitation", "statut"])]

    def __str__(self):
        return self.intitule
    @property
    def jours_avant_echeance(self):
        """Jours restants avant l'échéance ; négatif si elle est passée."""
        from django.utils import timezone

        if not self.date_fin:
            return None
        return (self.date_fin - timezone.localdate()).days

    @property
    def echeance_proche(self):
        """Vrai dans les soixante jours qui précèdent l'échéance.

        Le préavis de résiliation courant est de deux mois : au-delà, il est
        déjà trop tard pour changer d'assureur sans tacite reconduction.
        """
        restant = self.jours_avant_echeance
        return (self.statut == self.Statut.ACTIVE
                and restant is not None and 0 <= restant <= 60)

    @property
    def est_en_vigueur(self):
        """Active et non échue : la police sur laquelle on peut compter."""
        restant = self.jours_avant_echeance
        return self.statut == self.Statut.ACTIVE and (restant is None or restant >= 0)


class DocumentAssurance(models.Model):
    """Une pièce du dossier : la police, ses conditions, une attestation.

    Un contrat d'assurance n'est pas un formulaire, c'est une liasse. On garde
    les pièces telles quelles, et l'IA en tire les champs quand elle le peut.
    """

    class Type(models.TextChoices):
        POLICE = "police", _("Contrat / police")
        CONDITIONS = "conditions", _("Conditions générales")
        AVENANT = "avenant", _("Avenant")
        ATTESTATION = "attestation", _("Attestation")
        APPEL_PRIME = "appel_prime", _("Appel de prime")
        SINISTRE = "sinistre", _("Déclaration de sinistre")
        AUTRE = "autre", _("Autre")

    assurance = models.ForeignKey("contrat.Assurance", on_delete=models.CASCADE,
                                  related_name="documents")
    fichier = models.FileField(_("fichier"), upload_to="assurances/%Y/%m/")
    nom = models.CharField(_("nom"), max_length=255, blank=True)
    type_document = models.CharField(_("type"), max_length=15,
                                     choices=Type.choices, default=Type.POLICE)
    #: Ce que l'IA a lu du document, tel quel. Gardé pour qu'on puisse revenir
    #: sur ce qu'elle a proposé sans redemander une lecture.
    extraction = models.JSONField(_("extraction"), default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("document d'assurance")
        verbose_name_plural = _("documents d'assurance")
        ordering = ("-created_at",)

    def __str__(self):
        return self.nom or self.fichier.name


class Msa(models.Model):
    """Une cotisation / déclaration MSA (Mutualité Sociale Agricole)."""

    class TypeCotisation(models.TextChoices):
        AMEXA = "amexa", _("AMEXA — maladie exploitant")
        RETRAITE = "retraite", _("Retraite (AVI/AVA/RCO)")
        ATEXA = "atexa", _("ATEXA — accidents du travail")
        ALLOCATIONS = "allocations", _("Allocations familiales")
        CSG_CRDS = "csg_crds", _("CSG / CRDS")
        FORMATION = "formation", _("Formation (VIVEA)")
        SALARIES = "salaries", _("Cotisations salariés")
        AUTRE = "autre", _("Autre")

    class Statut(models.TextChoices):
        A_PAYER = "a_payer", _("À payer")
        PAYEE = "payee", _("Payée")
        EN_RETARD = "en_retard", _("En retard")
        EXONEREE = "exoneree", _("Exonérée")

    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE, related_name="cotisations_msa"
    )
    intitule = models.CharField(_("intitulé"), max_length=255)
    type_cotisation = models.CharField(
        _("type de cotisation"), max_length=15, choices=TypeCotisation.choices, default=TypeCotisation.AMEXA
    )
    numero_adherent = models.CharField(_("n° d'adhérent MSA"), max_length=50, blank=True)
    caisse = models.CharField(_("caisse MSA"), max_length=255, blank=True)
    montant = models.FloatField(_("montant (€)"), null=True, blank=True)
    periode = models.CharField(_("période / année"), max_length=50, blank=True)
    date_echeance = models.DateField(_("échéance"), null=True, blank=True)
    statut = models.CharField(_("statut"), max_length=12, choices=Statut.choices, default=Statut.A_PAYER)
    notes = models.TextField(_("notes"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("cotisation MSA")
        verbose_name_plural = _("cotisations MSA")
        ordering = ("-date_echeance", "-created_at")
        indexes = [models.Index(fields=["exploitation", "statut"])]

    def __str__(self):
        return self.intitule


class IndiceFermage(models.Model):
    """Indice national des fermages d'une année (variation en %).

    Publié chaque année par arrêté ministériel. Référentiel commun à toutes les
    exploitations : il n'est rattaché à aucune d'elles.
    """

    annee = models.PositiveIntegerField(_("année"), unique=True)
    variation_pct = models.DecimalField(
        _("variation (%)"), max_digits=6, decimal_places=2,
        help_text=_("Variation de l'indice par rapport à l'année précédente, ex. 1,62"),
    )
    reference = models.CharField(
        _("référence de l'arrêté"), max_length=255, blank=True,
        help_text=_("ex. arrêté du 15 juillet 2025"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("indice des fermages")
        verbose_name_plural = _("indices des fermages")
        ordering = ("-annee",)

    def __str__(self):
        return f"{self.annee} : {self.variation_pct} %"
