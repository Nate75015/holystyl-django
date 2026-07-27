from django.db import models
from django.utils.translation import gettext_lazy as _

from core.adresse import TYPES_VOIE


class Client(models.Model):
    """Un client de l'exploitation (acheteur de la production, prospect…)."""

    class Categorie(models.TextChoices):
        PARTICULIER = "particulier", _("Particulier")
        PROFESSIONNEL = "professionnel", _("Professionnel")

    class TypeClient(models.TextChoices):
        """Sous-catégories d'un client professionnel."""

        COOPERATIVE = "cooperative", _("Coopérative")
        GROSSISTE = "grossiste", _("Grossiste")
        DISTRIBUTEUR = "distributeur", _("Distributeur / GMS")
        RESTAURATION = "restauration", _("Restauration")
        COLLECTIVITE = "collectivite", _("Collectivité")
        EXPORT = "export", _("Export")
        AUTRE = "autre", _("Autre")

    class Statut(models.TextChoices):
        PROSPECT = "prospect", _("Prospect")
        ACTIF = "actif", _("Actif")
        INACTIF = "inactif", _("Inactif")
        ARCHIVE = "archive", _("Archivé")

    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE, related_name="clients"
    )
    nom = models.CharField(_("nom / raison sociale"), max_length=255)
    prenom = models.CharField(_("prénom"), max_length=255, blank=True)  # particuliers seulement
    categorie = models.CharField(
        _("catégorie"), max_length=15, choices=Categorie.choices, default=Categorie.PROFESSIONNEL
    )
    type_client = models.CharField(
        _("type"), max_length=15, choices=TypeClient.choices, default=TypeClient.AUTRE, blank=True
    )
    statut = models.CharField(
        _("statut"), max_length=10, choices=Statut.choices, default=Statut.PROSPECT
    )
    contact_principal = models.CharField(_("contact principal"), max_length=255, blank=True)
    email = models.EmailField(_("email"), blank=True)
    telephone = models.CharField(_("téléphone"), max_length=30, blank=True)
    site_web = models.CharField(_("site web"), max_length=255, blank=True)
    numero_voie = models.CharField(_("n° de voie"), max_length=10, blank=True)
    type_voie = models.CharField(_("catégorie de voie"), max_length=20, choices=TYPES_VOIE, blank=True)
    voie = models.CharField(_("voie"), max_length=255, blank=True)
    code_postal = models.CharField(_("code postal"), max_length=10, blank=True)
    ville = models.CharField(_("ville"), max_length=100, blank=True)
    pays = models.CharField(_("pays"), max_length=100, blank=True)
    siret = models.CharField(_("SIRET"), max_length=20, blank=True)
    tva_intracom = models.CharField(_("TVA intracommunautaire"), max_length=20, blank=True)
    delai_paiement_jours = models.PositiveIntegerField(
        _("délai de paiement (jours)"), null=True, blank=True
    )
    ca_annuel = models.FloatField(_("chiffre d'affaires annuel (€)"), null=True, blank=True)
    notes = models.TextField(_("notes"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("client")
        verbose_name_plural = _("clients")
        ordering = ("nom",)
        indexes = [models.Index(fields=["exploitation", "statut"])]

    def __str__(self):
        return self.nom_complet

    @property
    def est_particulier(self):
        return self.categorie == self.Categorie.PARTICULIER

    @property
    def nom_complet(self):
        """« Marie Dupont » pour un particulier, la raison sociale sinon."""
        if self.est_particulier and self.prenom:
            return f"{self.prenom} {self.nom}"
        return self.nom

    @property
    def type_label(self):
        """Libellé affiché : « Particulier », ou la sous-catégorie professionnelle."""
        if self.est_particulier:
            return self.get_categorie_display()
        return self.get_type_client_display() or self.get_categorie_display()

    @property
    def adresse_ligne(self):
        """Numéro, catégorie et nom de voie réunis (« 3 rue des Vergers »)."""
        parts = [self.numero_voie, self.get_type_voie_display() if self.type_voie else "", self.voie]
        return " ".join(part for part in parts if part)

    @property
    def adresse_complete(self):
        """Adresse sur une ligne (« 3 rue des Vergers, 84000 Avignon, France »)."""
        ville = " ".join(part for part in (self.code_postal, self.ville) if part)
        parts = [self.adresse_ligne, ville, self.pays]
        return ", ".join(part for part in parts if part)


class Partenaire(models.Model):
    """Un tiers de l'exploitation hors client : bailleur, comptable, avocat…

    Un seul modèle pour les trois : mêmes champs (identité, contact, adresse),
    seul le type change. Chaque type a sa page dans la section « Relations ».
    """

    class Type(models.TextChoices):
        BAILLEUR = "bailleur", _("Bailleur")
        COMPTABLE = "comptable", _("Comptable")
        AVOCAT = "avocat", _("Avocat")
        AUTRE = "autre", _("Autre")

    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE, related_name="partenaires"
    )
    type_partenaire = models.CharField(
        _("type"), max_length=15, choices=Type.choices, default=Type.AUTRE
    )
    nom = models.CharField(_("nom / raison sociale"), max_length=255)
    contact_principal = models.CharField(_("contact principal"), max_length=255, blank=True)
    email = models.EmailField(_("email"), blank=True)
    telephone = models.CharField(_("téléphone"), max_length=30, blank=True)
    site_web = models.CharField(_("site web"), max_length=255, blank=True)
    numero_voie = models.CharField(_("n° de voie"), max_length=10, blank=True)
    type_voie = models.CharField(_("catégorie de voie"), max_length=20, choices=TYPES_VOIE, blank=True)
    voie = models.CharField(_("voie"), max_length=255, blank=True)
    code_postal = models.CharField(_("code postal"), max_length=10, blank=True)
    ville = models.CharField(_("ville"), max_length=100, blank=True)
    siret = models.CharField(_("SIRET"), max_length=20, blank=True)
    notes = models.TextField(_("notes"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("partenaire")
        verbose_name_plural = _("partenaires")
        ordering = ("nom",)
        indexes = [models.Index(fields=["exploitation", "type_partenaire"])]

    def __str__(self):
        return self.nom

    @property
    def adresse_complete(self):
        """Adresse sur une ligne (« 3 rue des Vergers, 84000 Avignon »)."""
        voie = " ".join(p for p in (
            self.numero_voie,
            self.get_type_voie_display() if self.type_voie else "",
            self.voie,
        ) if p)
        commune = " ".join(p for p in (self.code_postal, self.ville) if p)
        return ", ".join(p for p in (voie, commune) if p)
