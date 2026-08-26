"""Vente directe — la boutique de la ferme et ce qu'elle propose.

Trois couches se suivent et ne se confondent pas : la parcelle produit
(`finances.Recolte`), le dépôt détient (`stock.Article`), la boutique propose
(`vente.Produit`). L'offre n'est donc pas l'article : on ne vend pas tout ce
qu'on détient — le GNR et les phytos n'ont rien à faire en ligne —, on ne vend
pas dans l'unité où l'on stocke (un colis de 5 kg contre du vrac au kilo), et
le prix de vente n'est pas le prix de revient. Le produit *pointe* vers
l'article : c'est là qu'il lit ce qu'il reste.
"""

import math
import uuid

from django.db import models
from django.db.models import FloatField, OuterRef, Subquery, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


def slug_unique(modele, base, champ="slug", exclure_pk=None, **filtres):
    """Slug lisible et libre, suffixé au besoin (« ferme-du-clos-2 »).

    `exclure_pk` écarte l'objet qu'on est en train de modifier : sans lui, une
    boutique qui réenregistre son propre slug se le verrait suffixer.
    """
    racine = slugify(base)[:120] or "boutique"
    candidat, rang = racine, 1
    requete = modele.objects.filter(**filtres)
    if exclure_pk:
        requete = requete.exclude(pk=exclure_pk)
    while requete.filter(**{champ: candidat}).exists():
        rang += 1
        candidat = f"{racine}-{rang}"
    return candidat


class Boutique(TimeStampedModel):
    """La vitrine publique d'une exploitation.

    Modèle distinct plutôt qu'une poignée de champs sur `Exploitation` :
    ouvrir une boutique est un acte volontaire — toutes les fermes ne vendent
    pas en direct — et `est_ouverte` doit pouvoir se refermer sans rien perdre.
    """

    exploitation = models.OneToOneField(
        "exploitations.Exploitation", on_delete=models.CASCADE, related_name="boutique"
    )
    slug = models.SlugField(_("adresse de la boutique"), max_length=140, unique=True)
    titre = models.CharField(_("nom public"), max_length=255, blank=True)
    accroche = models.CharField(_("accroche"), max_length=255, blank=True)
    description = models.TextField(_("présentation"), blank=True)

    #: Tant qu'elle est fermée, la boutique et ses produits n'existent pour
    #: personne : c'est l'interrupteur, et il est éteint par défaut.
    est_ouverte = models.BooleanField(_("boutique ouverte"), default=False)
    #: Ouverte, elle peut rester discrète : visible pour qui a le lien, sans
    #: figurer sur la place de marché commune.
    visible_marche = models.BooleanField(_("visible sur la place de marché"), default=True)

    retrait_ferme = models.BooleanField(_("retrait à la ferme"), default=True)
    adresse_retrait = models.CharField(_("lieu de retrait"), max_length=255, blank=True)
    horaires_retrait = models.CharField(_("horaires de retrait"), max_length=255, blank=True)
    livraison = models.BooleanField(_("livraison"), default=False)
    rayon_livraison_km = models.PositiveIntegerField(_("rayon de livraison (km)"), null=True, blank=True)
    zone_livraison = models.CharField(_("zone livrée"), max_length=255, blank=True)

    telephone = models.CharField(_("téléphone public"), max_length=30, blank=True)
    email = models.EmailField(_("email public"), blank=True)

    class Meta:
        verbose_name = _("boutique")
        verbose_name_plural = _("boutiques")
        ordering = ("titre",)

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slug_unique(Boutique, self.titre or self.exploitation.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("vente:boutique_publique", args=[self.slug])

    @property
    def nom(self):
        """Le nom public, à défaut celui de l'exploitation."""
        return self.titre or self.exploitation.name

    @property
    def localite(self):
        ville = self.exploitation.city or ""
        code = self.exploitation.postal_code or ""
        return f"{code} {ville}".strip()


class ProduitQuerySet(models.QuerySet):
    def publiables(self):
        """Ce qu'un visiteur a le droit de voir : en ligne, boutique ouverte, de saison."""
        aujourdhui = timezone.localdate()
        return (
            self.filter(statut=Produit.Statut.EN_LIGNE, exploitation__boutique__est_ouverte=True)
            .filter(models.Q(disponible_du=None) | models.Q(disponible_du__lte=aujourdhui))
            .filter(models.Q(disponible_au=None) | models.Q(disponible_au__gte=aujourdhui))
        )

    def sur_le_marche(self):
        """Ce qui remonte sur la place de marché commune (double opt-in)."""
        return self.publiables().filter(visible_marche=True, exploitation__boutique__visible_marche=True)

    def avec_reserve(self):
        """Annote la part de stock déjà promise par les commandes en cours.

        Sans cette annotation, afficher un catalogue rejouerait une requête par
        produit : la disponibilité sait s'en passer, mais au prix d'un N+1.
        """
        promis = (
            LigneCommande.objects.filter(
                article=OuterRef("article"), commande__statut__in=Commande.RESERVANTS
            )
            .values("article")
            .annotate(total=Sum("quantite_stock"))
            .values("total")
        )
        return self.annotate(
            _reserve=Coalesce(Subquery(promis, output_field=FloatField()), 0.0)
        )


class Produit(TimeStampedModel):
    """Une offre de la boutique, adossée à un article du stock."""

    class Categorie(models.TextChoices):
        LEGUME = "legume", _("Légumes")
        FRUIT = "fruit", _("Fruits")
        VIANDE = "viande", _("Viande")
        VOLAILLE = "volaille", _("Volaille")
        OEUF = "oeuf", _("Œufs")
        LAITIER = "laitier", _("Produits laitiers")
        FROMAGE = "fromage", _("Fromages")
        CEREALE = "cereale", _("Céréales et légumes secs")
        FARINE = "farine", _("Farines")
        HUILE = "huile", _("Huiles")
        MIEL = "miel", _("Miel")
        VIN = "vin", _("Vins et spiritueux")
        BOISSON = "boisson", _("Jus et boissons")
        EPICERIE = "epicerie", _("Épicerie et conserves")
        PLANT = "plant", _("Plants et semences")
        FLEUR = "fleur", _("Fleurs")
        FOURRAGE = "fourrage", _("Fourrage et paille")
        AUTRE = "autre", _("Autre")

    class UniteVente(models.TextChoices):
        KG = "kg", _("au kilo")
        PIECE = "piece", _("à la pièce")
        COLIS = "colis", _("le colis")
        PANIER = "panier", _("le panier")
        BARQUETTE = "barquette", _("la barquette")
        BOTTE = "botte", _("la botte")
        LITRE = "litre", _("le litre")
        BOUTEILLE = "bouteille", _("la bouteille")
        POT = "pot", _("le pot")
        DOUZAINE = "douzaine", _("la douzaine")
        SAC = "sac", _("le sac")

    class Statut(models.TextChoices):
        BROUILLON = "brouillon", _("Brouillon")
        EN_LIGNE = "en_ligne", _("En ligne")
        RETIRE = "retire", _("Retiré")

    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE, related_name="produits"
    )
    #: L'article qui fournit ce produit. Sans lui, l'offre reste affichable
    #: (vente sur commande, production à venir) mais ne sait plus dire ce qu'il
    #: reste : la disponibilité vaut alors None, pas zéro.
    article = models.ForeignKey(
        "stock.Article", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="produits", verbose_name=_("article de stock"),
    )
    nom = models.CharField(_("nom"), max_length=255)
    slug = models.SlugField(_("adresse"), max_length=160)
    categorie = models.CharField(
        _("catégorie"), max_length=12, choices=Categorie.choices, default=Categorie.AUTRE
    )
    description = models.TextField(_("description"), blank=True)
    photo = models.ImageField(_("photo"), upload_to="vente/produits/", null=True, blank=True)

    unite_vente = models.CharField(
        _("vendu"), max_length=12, choices=UniteVente.choices, default=UniteVente.KG
    )
    #: Combien d'unités de stock part une unité vendue — un colis de 5 kg vaut
    #: 5. C'est le pivot de conversion : sans lui, impossible de décompter le
    #: stock d'une commande de trois colis.
    conditionnement = models.FloatField(
        _("contenu"), default=1,
        help_text=_("Quantité prélevée sur le stock pour une unité vendue (ex. 5 pour un colis de 5 kg)."),
    )
    prix_ttc = models.FloatField(_("prix TTC (€)"), default=0)
    #: Le taux vit sur le produit et non sur la ferme : 5,5 % en alimentaire
    #: non transformé, 20 % sur le vin, les fleurs ou une prestation.
    taux_tva = models.FloatField(_("TVA (%)"), default=5.5)

    statut = models.CharField(_("statut"), max_length=10, choices=Statut.choices, default=Statut.BROUILLON)
    visible_marche = models.BooleanField(_("proposer sur la place de marché"), default=True)
    quantite_min = models.FloatField(_("commande minimum"), default=1)
    disponible_du = models.DateField(_("disponible à partir du"), null=True, blank=True)
    disponible_au = models.DateField(_("disponible jusqu'au"), null=True, blank=True)

    objects = ProduitQuerySet.as_manager()

    class Meta:
        verbose_name = _("produit")
        verbose_name_plural = _("produits")
        ordering = ("categorie", "nom")
        constraints = [
            models.UniqueConstraint(fields=["exploitation", "slug"], name="unique_produit_slug")
        ]
        indexes = [models.Index(fields=["exploitation", "statut"])]

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slug_unique(Produit, self.nom, exploitation=self.exploitation)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse

        # Un produit peut exister avant la boutique (brouillon saisi le premier
        # jour) : il n'a alors pas d'adresse publique, ce n'est pas une erreur.
        boutique = getattr(self.exploitation, "boutique", None)
        if boutique is None:
            return ""
        return reverse("vente:produit_public", args=[boutique.slug, self.slug])

    @property
    def reserve(self):
        """Quantité de stock déjà promise, dans l'unité de l'article."""
        annotee = getattr(self, "_reserve", None)
        if annotee is not None:
            return annotee
        if self.article_id is None:
            return 0
        total = LigneCommande.objects.filter(
            article_id=self.article_id, commande__statut__in=Commande.RESERVANTS
        ).aggregate(s=Sum("quantite_stock"))["s"]
        return total or 0

    @property
    def disponible(self):
        """Unités de vente encore vendables, ou None si l'offre ne suit pas de stock.

        None n'est pas zéro : un produit sans article est vendu sur commande,
        il ne doit pas s'afficher épuisé. Ce qui est déjà promis à d'autres
        acheteurs est déduit — le stock physique, lui, ne bougera qu'au retrait.
        """
        if self.article_id is None or not self.conditionnement:
            return None
        libre = (self.article.quantite or 0) - self.reserve
        return max(0, math.floor(libre / self.conditionnement))

    @property
    def est_epuise(self):
        disponible = self.disponible
        return disponible is not None and disponible <= 0

    @property
    def prix_ht(self):
        return self.prix_ttc / (1 + (self.taux_tva or 0) / 100)

    @property
    def unite_courte(self):
        """« /kg », « /pièce » — pour l'affichage du prix."""
        return dict(self.UniteVente.choices).get(self.unite_vente, "")


def numero_suivant(exploitation):
    """« CMD-2026-0007 » — numérotation continue par ferme et par année."""
    prefixe = f"CMD-{timezone.localdate().year}-"
    dernier = (
        Commande.objects.filter(exploitation=exploitation, numero__startswith=prefixe)
        .order_by("-numero")
        .values_list("numero", flat=True)
        .first()
    )
    rang = int(dernier.rsplit("-", 1)[1]) + 1 if dernier else 1
    return f"{prefixe}{rang:04d}"


class Commande(TimeStampedModel):
    """Une commande passée à une ferme depuis la vitrine.

    Une commande ne concerne **qu'une** ferme : le panier peut être multi-fermes,
    le retrait non. Un panier validé se scinde donc en autant de commandes que
    de producteurs, chacune avec son numéro et son créneau.
    """

    class Statut(models.TextChoices):
        NOUVELLE = "nouvelle", _("Nouvelle")
        CONFIRMEE = "confirmee", _("Confirmée")
        PRETE = "prete", _("Prête")
        SERVIE = "servie", _("Servie")
        REFUSEE = "refusee", _("Refusée")
        ANNULEE = "annulee", _("Annulée")

    class Retrait(models.TextChoices):
        FERME = "ferme", _("Retrait à la ferme")
        LIVRAISON = "livraison", _("Livraison")

    #: Statuts qui immobilisent de la marchandise : elle est promise à
    #: quelqu'un, sans être encore sortie du dépôt. Une commande est réservante
    #: dès sa réception : promettre deux fois le dernier colis en attendant que
    #: le paysan confirme ferait un déçu à coup sûr.
    RESERVANTS = (Statut.NOUVELLE, Statut.CONFIRMEE, Statut.PRETE)

    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE, related_name="commandes"
    )
    numero = models.CharField(_("numéro"), max_length=30)
    #: Adresse de suivi de l'acheteur, qui n'a pas de compte : imprévisible,
    #: donc un identifiant aléatoire plutôt que la clé primaire.
    jeton = models.UUIDField(_("jeton de suivi"), default=uuid.uuid4, unique=True, editable=False)

    client_ref = models.ForeignKey(
        "client.Client", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="commandes", verbose_name=_("fiche client"),
    )
    acheteur_nom = models.CharField(_("nom"), max_length=255)
    acheteur_email = models.EmailField(_("email"), blank=True)
    acheteur_telephone = models.CharField(_("téléphone"), max_length=30, blank=True)

    statut = models.CharField(_("statut"), max_length=10, choices=Statut.choices, default=Statut.NOUVELLE)
    mode_retrait = models.CharField(_("retrait"), max_length=10, choices=Retrait.choices, default=Retrait.FERME)
    adresse_livraison = models.TextField(_("adresse de livraison"), blank=True)
    date_souhaitee = models.DateField(_("date souhaitée"), null=True, blank=True)
    creneau = models.CharField(_("créneau"), max_length=100, blank=True)
    notes = models.TextField(_("message de l'acheteur"), blank=True)

    montant_ht = models.FloatField(_("total HT (€)"), default=0)
    montant_tva = models.FloatField(_("TVA (€)"), default=0)
    montant_ttc = models.FloatField(_("total TTC (€)"), default=0)

    #: Facture émise pour cette commande, quand elle l'a été. Toutes ne le sont
    #: pas : un particulier réglé au retrait n'en réclame pas toujours une.
    facture = models.OneToOneField(
        "finances.Facture", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="commande_vente", verbose_name=_("facture"),
    )

    confirmee_le = models.DateTimeField(null=True, blank=True)
    prete_le = models.DateTimeField(null=True, blank=True)
    servie_le = models.DateTimeField(null=True, blank=True)
    motif_refus = models.CharField(_("motif"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("commande")
        verbose_name_plural = _("commandes")
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(fields=["exploitation", "numero"], name="unique_commande_numero")
        ]
        indexes = [models.Index(fields=["exploitation", "statut", "-created_at"])]

    def __str__(self):
        return self.numero

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = numero_suivant(self.exploitation)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("vente:suivi", args=[self.jeton])

    @property
    def est_reservante(self):
        return self.statut in self.RESERVANTS

    @property
    def est_close(self):
        return self.statut in (self.Statut.SERVIE, self.Statut.REFUSEE, self.Statut.ANNULEE)

    def recalculer(self, enregistrer=True):
        """Repose les montants sur ses lignes (seule source de vérité)."""
        ttc = ht = 0
        for ligne in self.lignes.all():
            ttc += ligne.montant_ttc
            ht += ligne.montant_ht
        self.montant_ttc, self.montant_ht = round(ttc, 2), round(ht, 2)
        self.montant_tva = round(self.montant_ttc - self.montant_ht, 2)
        if enregistrer:
            self.save(update_fields=["montant_ht", "montant_tva", "montant_ttc", "updated_at"])
        return self.montant_ttc


class LigneCommande(models.Model):
    """Une ligne de commande, figée au moment où elle est passée.

    Le libellé, le prix et le conditionnement sont recopiés : le paysan doit
    pouvoir corriger son catalogue sans réécrire l'histoire des commandes déjà
    passées. `article` et `quantite_stock` disent quoi sortir du dépôt, et en
    quelle quantité, le jour du retrait.
    """

    commande = models.ForeignKey(Commande, on_delete=models.CASCADE, related_name="lignes")
    produit = models.ForeignKey(
        Produit, on_delete=models.SET_NULL, null=True, blank=True, related_name="lignes"
    )
    article = models.ForeignKey(
        "stock.Article", on_delete=models.SET_NULL, null=True, blank=True, related_name="lignes_vendues"
    )
    libelle = models.CharField(_("désignation"), max_length=255)
    unite_libelle = models.CharField(_("unité"), max_length=50, blank=True)
    quantite = models.FloatField(_("quantité"))
    #: Ce que la ligne prélève sur le stock, dans l'unité de l'article : trois
    #: colis de 5 kg immobilisent 15 kg, quel que soit le prix du colis.
    quantite_stock = models.FloatField(_("quantité prélevée"), default=0)
    prix_unitaire_ttc = models.FloatField(_("prix unitaire TTC (€)"), default=0)
    taux_tva = models.FloatField(_("TVA (%)"), default=5.5)

    class Meta:
        verbose_name = _("ligne de commande")
        verbose_name_plural = _("lignes de commande")
        ordering = ("id",)
        indexes = [models.Index(fields=["article"])]

    def __str__(self):
        return f"{self.quantite} × {self.libelle}"

    @property
    def montant_ttc(self):
        return round(self.quantite * self.prix_unitaire_ttc, 2)

    @property
    def montant_ht(self):
        return round(self.montant_ttc / (1 + (self.taux_tva or 0) / 100), 2)
