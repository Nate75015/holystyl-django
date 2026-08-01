"""Diagnostics Techniques d'Irrigation reçus de Cultiveau.

Cultiveau produit le DTI ; Holystyl le reçoit et l'exploite. Le contrat
d'échange est décrit dans `docs/schema-donnees.md` du dépôt Cultiveau : un
JSON hiérarchique signé, un objet par DTI, accompagné d'une archive de photos.

Trois partis pris structurent ces modèles.

**Le payload brut est conservé intégralement** dans `DtiImport.payload`. Les
modèles ci-dessous n'en extraient que ce que Holystyl exploite réellement ;
tout le reste reste lisible dans l'archive. On peut donc « promouvoir » plus
tard un morceau du payload en vrai modèle sans avoir à redemander l'export, et
sans avoir créé aujourd'hui vingt tables dont certaines ne serviraient jamais.

**Rien n'est dupliqué de ce que Holystyl sait déjà.** L'exploitation, les
parcelles, leurs campagnes, les analyses NDVI et le score DTI ont leurs modèles
ici depuis longtemps : l'import les alimente au lieu d'en créer des jumeaux.
Seul ce qui n'existait pas — ressources en eau, canalisations, matériel
d'irrigation et relevés — arrive avec cette app.

**Chaque réception est un instantané daté.** Un diagnostic est un constat à une
date ; comparer l'état d'un réseau entre deux passages a de la valeur. Les
objets d'un DTI appartiennent donc à leur `DtiImport` et ne sont jamais écrasés
par la réception suivante. L'état courant, c'est le dernier import en date.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


class DtiImport(TimeStampedModel):
    """Une réception de DTI : archive brute, traçabilité et rattachement.

    Le courriel n'authentifie pas son expéditeur : `empreinte` et la
    vérification de signature à l'import sont ce qui distingue un diagnostic
    légitime d'un dépôt arbitraire dans la boîte de réception.
    """

    class Statut(models.TextChoices):
        RECU = "recu", _("Reçu")
        IMPORTE = "importe", _("Importé")
        QUARANTAINE = "quarantaine", _("En attente de rattachement")
        REJETE = "rejete", _("Rejeté")
        ERREUR = "erreur", _("Erreur")

    # ── Provenance ──
    source = models.CharField(_("source"), max_length=50, default="cultiveau")
    schema_version = models.CharField(_("version du schéma"), max_length=10)
    dti_source_id = models.PositiveIntegerField(
        _("identifiant du DTI à la source"), null=True, blank=True,
        help_text=_("Identifiant de corrélation, pas une clé étrangère."))
    exported_at = models.DateTimeField(_("exporté le"), null=True, blank=True)
    recu_le = models.DateTimeField(_("reçu le"), auto_now_add=True)

    #: SHA-256 du contenu métier, calculé par la source. Deux réceptions de
    #: même empreinte portent le même diagnostic : c'est ce qui permet de
    #: reconnaître un renvoi sans rejouer tout l'import.
    empreinte = models.CharField(_("empreinte du contenu"), max_length=64, db_index=True)

    # ── Contenu ──
    payload = models.JSONField(
        _("payload"), default=dict,
        help_text=_("Archive intégrale telle que reçue, y compris ce que "
                    "Holystyl n'exploite pas encore."))

    # ── Rattachement ──
    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE,
        related_name="dti_imports", null=True, blank=True,
        verbose_name=_("exploitation"))
    #: Recopiés du payload pour permettre le rattachement manuel : sans
    #: exploitation liée, ce sont les seuls repères pour retrouver de qui il
    #: s'agit.
    siret_declare = models.CharField(_("SIRET déclaré"), max_length=14, blank=True)
    nom_declare = models.CharField(_("nom déclaré"), max_length=255, blank=True)

    # ── Suivi ──
    statut = models.CharField(_("statut"), max_length=12,
                              choices=Statut.choices, default=Statut.RECU)
    erreur = models.TextField(_("erreur"), blank=True)
    rapport = models.JSONField(
        _("rapport d'import"), default=dict, blank=True,
        help_text=_("Ce qui a été créé, par modèle — pour vérifier qu'un "
                    "import n'a pas silencieusement rien fait."))

    # ── Médias ──
    medias_archive = models.JSONField(_("archive des médias"), null=True, blank=True)
    medias_recuperes = models.BooleanField(_("médias récupérés"), default=False)

    class Meta:
        ordering = ("-recu_le",)
        verbose_name = _("import de DTI")
        verbose_name_plural = _("imports de DTI")
        indexes = [models.Index(fields=["siret_declare", "-recu_le"])]

    def __str__(self):
        return f"DTI {self.dti_source_id or '?'} · {self.nom_declare or self.siret_declare or '—'}"

    @property
    def en_quarantaine(self):
        return self.statut == self.Statut.QUARANTAINE


class ElementDti(TimeStampedModel):
    """Socle des objets appartenant à un import.

    `exploitation` est dénormalisée depuis l'import : sans elle, toute
    requête métier (« toutes les bornes de cette exploitation ») imposerait de
    passer par l'import à chaque fois. Elle est renseignée au rattachement.
    """

    import_dti = models.ForeignKey(
        DtiImport, on_delete=models.CASCADE, related_name="%(class)ss",
        verbose_name=_("import"))
    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE,
        related_name="%(class)ss_dti", null=True, blank=True,
        verbose_name=_("exploitation"))
    #: Identifiant de l'objet chez la source, conservé pour relier les objets
    #: entre eux à l'import et pour retrouver l'original en cas de litige.
    source_id = models.PositiveIntegerField(_("id source"), null=True, blank=True)

    class Meta:
        abstract = True


class RessourceEau(ElementDti):
    """Point de prélèvement ou borne d'irrigation.

    Les deux partagent une table, comme à la source : ce sont deux natures du
    même objet — d'où l'eau vient, et où on la prend pour irriguer.
    """

    class Categorie(models.TextChoices):
        PRELEVEMENT = "prelevement", _("Point d'eau (prélèvement)")
        BORNE = "borne", _("Borne d'irrigation")

    categorie = models.CharField(_("catégorie"), max_length=20,
                                 choices=Categorie.choices, default=Categorie.PRELEVEMENT)
    nom = models.CharField(_("désignation"), max_length=120)
    type_ressource = models.CharField(_("type"), max_length=40, blank=True)
    parcelle = models.ForeignKey(
        "parcelles.Parcelle", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ressources_dti", verbose_name=_("parcelle"))

    volume_autorise_m3 = models.DecimalField(
        _("volume autorisé (m³/an)"), max_digits=12, decimal_places=2, null=True, blank=True)
    debit_max_m3h = models.DecimalField(
        _("débit max (m³/h)"), max_digits=8, decimal_places=2, null=True, blank=True)
    diametre_dn_mm = models.PositiveIntegerField(_("DN (mm)"), null=True, blank=True)
    pression_requise_bar = models.DecimalField(
        _("pression requise (bar)"), max_digits=5, decimal_places=2, null=True, blank=True)
    profondeur_m = models.DecimalField(
        _("profondeur (m)"), max_digits=7, decimal_places=2, null=True, blank=True)
    numero_point = models.CharField(_("n° de point / compteur"), max_length=60, blank=True)

    # Qualité de l'eau — ce qui pilote les alertes de colmatage des goutteurs.
    durete_th = models.DecimalField(_("dureté (°f)"), max_digits=5, decimal_places=1,
                                    null=True, blank=True)
    ph = models.DecimalField(_("pH"), max_digits=4, decimal_places=1, null=True, blank=True)
    fer_mg_l = models.DecimalField(_("fer (mg/L)"), max_digits=5, decimal_places=2,
                                   null=True, blank=True)
    matieres_suspension = models.CharField(_("matières en suspension"), max_length=10, blank=True)

    latitude = models.FloatField(_("latitude"), null=True, blank=True)
    longitude = models.FloatField(_("longitude"), null=True, blank=True)
    cadastral_ref = models.CharField(_("réf. cadastrale"), max_length=50, blank=True)
    commune = models.CharField(_("commune"), max_length=120, blank=True)
    notes = models.TextField(_("notes"), blank=True)

    class Meta:
        ordering = ("nom",)
        verbose_name = _("ressource en eau")
        verbose_name_plural = _("ressources en eau")

    def __str__(self):
        return self.nom


class Canalisation(ElementDti):
    """Tronçon du réseau de transport."""

    nom = models.CharField(_("désignation"), max_length=120, blank=True)
    ordre = models.PositiveIntegerField(_("ordre amont → aval"), null=True, blank=True)
    parcelle = models.ForeignKey(
        "parcelles.Parcelle", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="canalisations_dti", verbose_name=_("parcelle"))

    diametre_mm = models.DecimalField(_("Ø extérieur (mm)"), max_digits=7, decimal_places=1,
                                      null=True, blank=True)
    diametre_int_mm = models.DecimalField(_("Ø intérieur (mm)"), max_digits=7, decimal_places=1,
                                          null=True, blank=True)
    materiau = models.CharField(_("matériau"), max_length=60, blank=True)
    longueur_m = models.DecimalField(_("longueur (m)"), max_digits=10, decimal_places=1,
                                     null=True, blank=True)
    debit_m3h = models.DecimalField(_("débit (m³/h)"), max_digits=8, decimal_places=2,
                                    null=True, blank=True)
    #: Géométrie GeoJSON du tracé, telle qu'émise par la source.
    geometry = models.JSONField(_("tracé"), null=True, blank=True)

    class Meta:
        ordering = ("ordre", "id")
        verbose_name = _("canalisation")
        verbose_name_plural = _("canalisations")

    def __str__(self):
        return self.nom or f"Tronçon {self.ordre or self.pk}"


class Equipement(ElementDti):
    """Matériel d'irrigation.

    À la source, cette table est polymorphe : 175 colonnes couvrant dix-huit
    types de matériel, dont environ 90 % sont vides pour un objet donné. Les
    recopier ici produirait une table illisible et un couplage fort à chaque
    évolution de Cultiveau.

    On garde donc en colonnes ce qui est commun à tous les types — et donc
    requêtable : identité, état, position, rattachement. Le reste, spécifique
    au type, atterrit dans `caracteristiques`, avec ses noms de champs
    d'origine. Rien n'est perdu, et promouvoir un attribut en colonne le jour
    où on veut le requêter reste une migration simple.
    """

    class Categorie(models.TextChoices):
        FIXE = "fixe", _("Fixe")
        MOBILE = "mobile", _("Mobile")

    nom = models.CharField(_("désignation"), max_length=200, blank=True)
    type_equipement = models.CharField(_("type"), max_length=80, blank=True, db_index=True)
    categorie = models.CharField(_("catégorie"), max_length=10,
                                 choices=Categorie.choices, blank=True)
    marque = models.CharField(_("marque"), max_length=120, blank=True)
    modele = models.CharField(_("modèle"), max_length=120, blank=True)
    annee = models.PositiveIntegerField(_("année"), null=True, blank=True)
    etat = models.CharField(_("état"), max_length=40, blank=True)

    parcelle = models.ForeignKey(
        "parcelles.Parcelle", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="equipements_dti", verbose_name=_("parcelle"))
    parcelles_desservies = models.ManyToManyField(
        "parcelles.Parcelle", blank=True, related_name="equipements_dti_desservis",
        verbose_name=_("parcelles desservies"))
    borne_source = models.ForeignKey(
        RessourceEau, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="equipements_alimentes", verbose_name=_("borne d'alimentation"))

    latitude = models.FloatField(_("latitude"), null=True, blank=True)
    longitude = models.FloatField(_("longitude"), null=True, blank=True)

    caracteristiques = models.JSONField(
        _("caractéristiques"), default=dict, blank=True,
        help_text=_("Champs propres au type de matériel, sous leurs noms "
                    "d'origine à la source."))

    class Meta:
        ordering = ("type_equipement", "nom")
        verbose_name = _("équipement")
        verbose_name_plural = _("équipements")

    def __str__(self):
        return self.nom or self.type_equipement or f"Équipement {self.pk}"


class Composant(ElementDti):
    """Pièce montée sur une borne ou sur une station de pompage.

    La source en tient deux tables, une par porteur. Elles décrivent la même
    chose — une pièce, sa marque, son état — et les distinguer ici ferait deux
    modèles jumeaux pour une seule question métier : « qu'y a-t-il sur cet
    organe ? ». Le porteur est donc une relation, pas un type.
    """

    ressource = models.ForeignKey(
        RessourceEau, on_delete=models.CASCADE, related_name="composants",
        null=True, blank=True, verbose_name=_("borne"))
    equipement = models.ForeignKey(
        Equipement, on_delete=models.CASCADE, related_name="composants",
        null=True, blank=True, verbose_name=_("équipement"))

    type_composant = models.CharField(_("type"), max_length=120, blank=True)
    marque = models.CharField(_("marque"), max_length=120, blank=True)
    modele = models.CharField(_("modèle"), max_length=120, blank=True)
    etat = models.CharField(_("état"), max_length=40, blank=True)
    diametre_mm = models.PositiveIntegerField(_("Ø (mm)"), null=True, blank=True)
    catalogue_ref = models.CharField(_("référence catalogue"), max_length=120, blank=True)
    notes = models.TextField(_("notes"), blank=True)
    caracteristiques = models.JSONField(_("caractéristiques"), default=dict, blank=True)

    class Meta:
        verbose_name = _("composant")
        verbose_name_plural = _("composants")
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(ressource__isnull=False, equipement__isnull=True)
                    | models.Q(ressource__isnull=True, equipement__isnull=False)
                ),
                name="composant_un_seul_porteur",
                violation_error_message=_(
                    "Un composant est monté soit sur une borne, soit sur un "
                    "équipement — jamais sur les deux ni sur aucun."),
            ),
        ]

    def __str__(self):
        return self.type_composant or f"Composant {self.pk}"


class MesureDebit(ElementDti):
    """Relevé de débit daté, sur une borne, un équipement ou un tronçon."""

    date = models.DateField(_("date"), null=True, blank=True)
    ressource = models.ForeignKey(
        RessourceEau, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="mesures_debit", verbose_name=_("ressource"))
    equipement = models.ForeignKey(
        Equipement, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="mesures_debit", verbose_name=_("équipement"))
    canalisation = models.ForeignKey(
        Canalisation, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="mesures_debit", verbose_name=_("canalisation"))

    point_libelle = models.CharField(_("point de mesure"), max_length=200, blank=True)
    methode = models.CharField(_("méthode"), max_length=80, blank=True)
    debit_m3h = models.DecimalField(_("débit (m³/h)"), max_digits=8, decimal_places=2,
                                    null=True, blank=True)
    pression_bar = models.DecimalField(_("pression (bar)"), max_digits=5, decimal_places=2,
                                       null=True, blank=True)
    notes = models.TextField(_("notes"), blank=True)

    class Meta:
        ordering = ("-date",)
        verbose_name = _("mesure de débit")
        verbose_name_plural = _("mesures de débit")


class MesureElectrique(ElementDti):
    """Relevé électrique historisé d'une pompe — support du diagnostic de vétusté."""

    equipement = models.ForeignKey(
        Equipement, on_delete=models.CASCADE, related_name="mesures_electriques",
        verbose_name=_("équipement"))
    date = models.DateField(_("date"), null=True, blank=True)
    isolement_mohm = models.DecimalField(_("isolement (MΩ)"), max_digits=8, decimal_places=2,
                                         null=True, blank=True)
    intensite_a = models.DecimalField(_("intensité (A)"), max_digits=8, decimal_places=2,
                                      null=True, blank=True)
    tension_v = models.DecimalField(_("tension (V)"), max_digits=8, decimal_places=2,
                                    null=True, blank=True)
    caracteristiques = models.JSONField(_("relevés détaillés"), default=dict, blank=True)

    class Meta:
        ordering = ("-date",)
        verbose_name = _("mesure électrique")
        verbose_name_plural = _("mesures électriques")


class MediaDti(TimeStampedModel):
    """Photo ou carte rattachée à un objet du DTI.

    Le chemin d'origine (`chemin_source`) est conservé : c'est la clé qui relie
    le binaire de l'archive à l'objet qui le porte, sans table de
    correspondance.
    """

    import_dti = models.ForeignKey(DtiImport, on_delete=models.CASCADE,
                                   related_name="medias", verbose_name=_("import"))
    chemin_source = models.CharField(_("chemin à la source"), max_length=300)
    fichier = models.FileField(_("fichier"), upload_to="dti/%Y/%m/", blank=True)
    sha256 = models.CharField(_("empreinte"), max_length=64, blank=True)
    octets = models.PositiveIntegerField(_("taille"), null=True, blank=True)
    legende = models.CharField(_("légende"), max_length=200, blank=True)
    #: Modèle et identifiant source du porteur (parcelle, borne, équipement…).
    porteur_type = models.CharField(_("type de porteur"), max_length=60, blank=True)
    porteur_source_id = models.PositiveIntegerField(_("id source du porteur"),
                                                    null=True, blank=True)
    manquant = models.BooleanField(
        _("absent à la source"), default=False,
        help_text=_("Référencé par le diagnostic mais introuvable au moment "
                    "de l'export — à distinguer d'une absence de photo."))

    class Meta:
        verbose_name = _("média de DTI")
        verbose_name_plural = _("médias de DTI")

    def __str__(self):
        return self.chemin_source
