"""Stock — inventaire de l'exploitation : dépôts, articles et mouvements.

Le niveau d'un article est porté par l'article lui-même (`Article.quantite`)
et n'est jamais écrit à la main : seul un `Mouvement` le déplace, et chaque
mouvement garde le niveau atteint (`quantite_apres`). Le journal se lit donc
tel quel, sans rejouer l'historique à chaque affichage, et une ligne isolée
suffit à dire ce que valait le stock ce jour-là.
"""

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


class Unite(models.TextChoices):
    """Unités de tenue de stock, communes aux articles et aux mouvements."""

    KG = "kg", _("kg")
    TONNE = "t", _("t")
    LITRE = "l", _("L")
    HECTOLITRE = "hl", _("hL")
    M3 = "m3", _("m³")
    UNITE = "unite", _("unité")
    SAC = "sac", _("sac")
    BIG_BAG = "big_bag", _("big bag")
    PALETTE = "palette", _("palette")
    DOSE = "dose", _("dose")


class Depot(TimeStampedModel):
    """Un lieu de stockage : hangar, silo, cuve, chambre froide, local phyto."""

    class TypeDepot(models.TextChoices):
        HANGAR = "hangar", _("Hangar")
        SILO = "silo", _("Silo")
        CUVE = "cuve", _("Cuve")
        CHAMBRE_FROIDE = "chambre_froide", _("Chambre froide")
        LOCAL_PHYTO = "local_phyto", _("Local phytosanitaire")
        MAGASIN = "magasin", _("Magasin")
        EXTERIEUR = "exterieur", _("Extérieur")
        AUTRE = "autre", _("Autre")

    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE, related_name="depots"
    )
    nom = models.CharField(_("nom"), max_length=255)
    type_depot = models.CharField(
        _("type"), max_length=20, choices=TypeDepot.choices, default=TypeDepot.HANGAR
    )
    localisation = models.CharField(_("localisation"), max_length=255, blank=True)
    capacite = models.FloatField(_("capacité"), null=True, blank=True)
    unite_capacite = models.CharField(
        _("unité de capacité"), max_length=10, choices=Unite.choices, blank=True
    )
    notes = models.TextField(_("notes"), blank=True)

    class Meta:
        verbose_name = _("dépôt")
        verbose_name_plural = _("dépôts")
        ordering = ("nom",)
        indexes = [models.Index(fields=["exploitation", "type_depot"])]

    def __str__(self):
        return self.nom


class Article(TimeStampedModel):
    """Un produit tenu en stock : intrant, récolte, pièce, emballage…"""

    class Categorie(models.TextChoices):
        SEMENCE = "semence", _("Semences et plants")
        ENGRAIS = "engrais", _("Engrais")
        AMENDEMENT = "amendement", _("Amendements")
        PHYTO = "phyto", _("Produits phytosanitaires")
        BIOCONTROLE = "biocontrole", _("Biocontrôle")
        ALIMENT = "aliment", _("Aliments du bétail")
        LITIERE = "litiere", _("Litière et fourrage")
        VETERINAIRE = "veterinaire", _("Produits vétérinaires")
        CARBURANT = "carburant", _("Carburants et lubrifiants")
        PIECE = "piece", _("Pièces détachées")
        EMBALLAGE = "emballage", _("Emballages")
        RECOLTE = "recolte", _("Récolte")
        AUTRE = "autre", _("Autre")

    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE, related_name="articles_stock"
    )
    # Un dépôt supprimé ne doit pas emporter le stock qu'il contenait : les
    # articles restent, simplement sans emplacement.
    depot = models.ForeignKey(
        Depot, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="articles", verbose_name=_("dépôt"),
    )
    nom = models.CharField(_("désignation"), max_length=255)
    reference = models.CharField(_("référence"), max_length=100, blank=True)
    categorie = models.CharField(
        _("catégorie"), max_length=15, choices=Categorie.choices, default=Categorie.AUTRE
    )
    unite = models.CharField(_("unité"), max_length=10, choices=Unite.choices, default=Unite.KG)
    quantite = models.FloatField(_("quantité en stock"), default=0)
    seuil_alerte = models.FloatField(_("seuil d'alerte"), null=True, blank=True)
    prix_unitaire = models.FloatField(_("prix unitaire (€)"), null=True, blank=True)
    fournisseur = models.CharField(_("fournisseur"), max_length=255, blank=True)
    lot = models.CharField(_("n° de lot"), max_length=100, blank=True)
    date_peremption = models.DateField(_("date de péremption"), null=True, blank=True)
    notes = models.TextField(_("notes"), blank=True)

    class Meta:
        verbose_name = _("article")
        verbose_name_plural = _("articles")
        ordering = ("nom",)
        indexes = [models.Index(fields=["exploitation", "categorie"])]

    def __str__(self):
        return self.nom

    @property
    def valeur(self):
        """Valeur du stock détenu (€), 0 tant qu'aucun prix n'est renseigné."""
        return (self.quantite or 0) * (self.prix_unitaire or 0)

    @property
    def en_alerte(self):
        """Sous le seuil de réapprovisionnement — sans seuil, pas d'alerte."""
        return self.seuil_alerte is not None and (self.quantite or 0) <= self.seuil_alerte

    @property
    def perime(self):
        return self.date_peremption is not None and self.date_peremption < timezone.localdate()


class Mouvement(TimeStampedModel):
    """Une entrée, une sortie ou une correction d'inventaire sur un article."""

    class Type(models.TextChoices):
        ENTREE = "entree", _("Entrée")
        SORTIE = "sortie", _("Sortie")
        #: La quantité saisie n'est pas un écart mais le niveau constaté au
        #: comptage : c'est le stock théorique qui s'aligne, pas l'inverse.
        CORRECTION = "correction", _("Correction d'inventaire")

    class Motif(models.TextChoices):
        ACHAT = "achat", _("Achat")
        RECOLTE = "recolte", _("Récolte rentrée")
        RETOUR = "retour", _("Retour de chantier")
        EPANDAGE = "epandage", _("Épandage / traitement")
        SEMIS = "semis", _("Semis / plantation")
        ALIMENTATION = "alimentation", _("Alimentation du bétail")
        VENTE = "vente", _("Vente")
        PERTE = "perte", _("Perte, casse ou péremption")
        INVENTAIRE = "inventaire", _("Inventaire")
        AUTRE = "autre", _("Autre")

    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE, related_name="mouvements_stock"
    )
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="mouvements")
    type_mouvement = models.CharField(
        _("sens"), max_length=12, choices=Type.choices, default=Type.SORTIE
    )
    motif = models.CharField(_("motif"), max_length=15, choices=Motif.choices, default=Motif.AUTRE)
    quantite = models.FloatField(_("quantité"))
    quantite_apres = models.FloatField(_("stock après mouvement"), default=0)
    date = models.DateTimeField(_("date"), default=timezone.now)
    cout_unitaire = models.FloatField(_("coût unitaire (€)"), null=True, blank=True)
    # La sortie d'un intrant se rattache à la parcelle qui l'a reçu : c'est ce
    # qui permettra plus tard d'imputer les charges à la bonne culture.
    parcelle = models.ForeignKey(
        "parcelles.Parcelle", on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_("parcelle"),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    # Récolte dont cette entrée provient. C'est le fil qui relie un lot en
    # dépôt à la parcelle qui l'a produit — la traçabilité que réclamera la
    # vente en direct, et que ni l'un ni l'autre des deux modèles ne porte seul.
    recolte = models.ForeignKey(
        "finances.Recolte", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="entrees_stock", verbose_name=_("récolte d'origine"),
    )
    notes = models.TextField(_("notes"), blank=True)

    class Meta:
        verbose_name = _("mouvement de stock")
        verbose_name_plural = _("mouvements de stock")
        ordering = ("-date", "-created_at")
        indexes = [
            models.Index(fields=["exploitation", "-date"]),
            models.Index(fields=["article", "-date"]),
        ]

    def __str__(self):
        return f"{self.get_type_mouvement_display()} — {self.article} ({self.quantite})"

    def niveau_apres(self, depuis=None):
        """Niveau de l'article une fois ce mouvement appliqué.

        `depuis` permet de partir d'un stock déjà lu (verrouillé) plutôt que de
        relire l'article.
        """
        actuel = self.article.quantite if depuis is None else depuis
        actuel = actuel or 0
        if self.type_mouvement == self.Type.ENTREE:
            return actuel + self.quantite
        if self.type_mouvement == self.Type.SORTIE:
            return actuel - self.quantite
        return self.quantite

    def save(self, *args, **kwargs):
        """Enregistre le mouvement **et** déplace le stock de l'article.

        Les deux vont ensemble : un mouvement écrit sans que l'article suive
        laisserait un journal qui ment. Le verrou sur l'article sérialise deux
        sorties simultanées, qui sinon partiraient du même stock de départ.
        """
        if not self._state.adding:
            super().save(*args, **kwargs)
            return

        with transaction.atomic():
            stock = (
                Article.objects.select_for_update()
                .filter(pk=self.article_id)
                .values_list("quantite", flat=True)
                .first()
            )
            self.quantite_apres = self.niveau_apres(depuis=stock)
            super().save(*args, **kwargs)
            Article.objects.filter(pk=self.article_id).update(
                quantite=self.quantite_apres, updated_at=timezone.now()
            )
            self.article.quantite = self.quantite_apres
