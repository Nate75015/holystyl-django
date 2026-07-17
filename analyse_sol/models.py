"""Analyses de sol — analyses chimiques de sol par parcelle."""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import get_valid_filename
from django.utils.translation import gettext_lazy as _


def document_upload_path(instance, filename):
    """Range le document dans : analyses_sol/<parcelle>/<année>/<mois>/<fichier>."""
    parcelle = getattr(instance.parcelle, "name", "") or "parcelle"
    parcelle = get_valid_filename(parcelle) or "parcelle"
    d = instance.date or timezone.now()
    return f"analyses_sol/{parcelle}/{d:%Y}/{d:%m}/{get_valid_filename(filename)}"


class AnalyseSol(models.Model):
    """Analyse chimique de sol saisie manuellement."""

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="analyses_sol")
    parcelle = models.ForeignKey("parcelles.Parcelle", on_delete=models.CASCADE, related_name="analyses_sol")
    date = models.DateTimeField()

    # ── Identification du rapport (d'après le bordereau labo, ex. AUREA) ──
    laboratoire = models.CharField(_("laboratoire"), max_length=255, blank=True)
    numero_laboratoire = models.CharField(_("n° laboratoire"), max_length=50, blank=True)
    reference = models.CharField(_("référence"), max_length=255, blank=True)
    technicien = models.CharField(_("technicien"), max_length=255, blank=True)
    commune = models.CharField(_("commune"), max_length=255, blank=True)
    profondeur_prelevement = models.CharField(_("profondeur de prélèvement"), max_length=50, blank=True)
    date_prelevement = models.DateField(_("prélevé le"), null=True, blank=True)
    date_arrivee_labo = models.DateField(_("arrivée labo"), null=True, blank=True)
    date_expedition = models.DateField(_("sortie labo"), null=True, blank=True)

    # ── pH & calcaire ──
    ph = models.FloatField(_("pH eau"), null=True, blank=True)
    ph_kcl = models.FloatField(_("pH KCl"), null=True, blank=True)
    ec = models.FloatField(_("conductivité (mS/cm)"), null=True, blank=True)
    calcaire_total = models.FloatField(_("calcaire total (%)"), null=True, blank=True)
    calcaire_actif = models.FloatField(_("calcaire actif (% sec)"), null=True, blank=True)
    calcium_cao = models.FloatField(_("calcium CaO (mg/kg)"), null=True, blank=True)

    # ── Matière organique, carbone & azote ──
    matiere_organique = models.FloatField(_("matière organique (%)"), null=True, blank=True)
    carbone_organique = models.FloatField(_("carbone organique (%)"), null=True, blank=True)
    azote_total = models.FloatField(_("azote total N (%)"), null=True, blank=True)
    c_n = models.FloatField(_("rapport C/N"), null=True, blank=True)
    coefficient_k2 = models.FloatField(_("coefficient K2 (%)"), null=True, blank=True)
    azote_ammoniacal = models.FloatField(_("azote ammoniacal N-NH4 (mg/kg)"), null=True, blank=True)

    # ── Éléments majeurs (mg/kg) ──
    phosphore_assimilable = models.FloatField(_("phosphore P2O5 (mg/kg)"), null=True, blank=True)
    phosphore_olsen = models.FloatField(_("phosphore Olsen (mg/kg)"), null=True, blank=True)
    potassium_echangeable = models.FloatField(_("potasse K2O (mg/kg)"), null=True, blank=True)
    magnesium_mgo = models.FloatField(_("magnésie MgO (mg/kg)"), null=True, blank=True)
    sodium_na2o = models.FloatField(_("sodium Na2O (mg/kg)"), null=True, blank=True)

    # ── Oligo-éléments (mg/kg) ──
    bore = models.FloatField(_("bore B (mg/kg)"), null=True, blank=True)
    cuivre = models.FloatField(_("cuivre Cu EDTA (mg/kg)"), null=True, blank=True)
    fer = models.FloatField(_("fer Fe EDTA (mg/kg)"), null=True, blank=True)
    manganese = models.FloatField(_("manganèse Mn EDTA (mg/kg)"), null=True, blank=True)
    zinc = models.FloatField(_("zinc Zn EDTA (mg/kg)"), null=True, blank=True)

    # ── CEC & équilibre cationique ──
    cec = models.FloatField(_("CEC (meq/100g)"), null=True, blank=True)
    taux_saturation = models.CharField(_("taux de saturation (%)"), max_length=20, blank=True)
    ca_cec = models.FloatField(_("Ca/CEC (%)"), null=True, blank=True)
    k_cec = models.FloatField(_("K/CEC (%)"), null=True, blank=True)
    mg_cec = models.FloatField(_("Mg/CEC (%)"), null=True, blank=True)
    na_cec = models.FloatField(_("Na/CEC (%)"), null=True, blank=True)
    h_cec = models.FloatField(_("H/CEC (%)"), null=True, blank=True)

    # ── Granulométrie / texture (%) ──
    type_sol = models.CharField(_("type de sol"), max_length=100, blank=True)
    argile = models.FloatField(_("argile (%)"), null=True, blank=True)
    limons_fins = models.FloatField(_("limons fins (%)"), null=True, blank=True)
    limons_grossiers = models.FloatField(_("limons grossiers (%)"), null=True, blank=True)
    sables_fins = models.FloatField(_("sables fins (%)"), null=True, blank=True)
    sables_grossiers = models.FloatField(_("sables grossiers (%)"), null=True, blank=True)

    # ── Propriétés physiques & réserve en eau ──
    humidite = models.FloatField(_("humidité sur brut (%)"), null=True, blank=True)
    matiere_seche = models.FloatField(_("matière sèche sur brut (%)"), null=True, blank=True)
    refus_2mm = models.FloatField(_("refus à 2 mm (%)"), null=True, blank=True)
    densite_apparente = models.FloatField(_("densité apparente (g/cm³)"), null=True, blank=True)
    reserve_utile = models.FloatField(_("réserve utile RU (mm/cm)"), null=True, blank=True)
    reserve_facilement_utilisable = models.FloatField(_("réserve facilement utilisable RFU (mm/cm)"), null=True, blank=True)
    capacite_retention_pf25 = models.FloatField(_("rétention en eau à pF 2.5 (% MS)"), null=True, blank=True)
    capacite_retention_pf42 = models.FloatField(_("rétention en eau à pF 4.2 (% MS)"), null=True, blank=True)
    indice_battance = models.FloatField(_("indice de battance"), null=True, blank=True)
    risque_battance = models.CharField(_("risque de battance"), max_length=50, blank=True)

    # ── Éléments traces métalliques (mg/kg MS sauf indication) ──
    cadmium = models.FloatField(_("cadmium (mg/kg MS)"), null=True, blank=True)
    chrome = models.FloatField(_("chrome (mg/kg MS)"), null=True, blank=True)
    cuivre_total = models.FloatField(_("cuivre total (mg/kg MS)"), null=True, blank=True)
    mercure = models.FloatField(_("mercure (mg/kg MS)"), null=True, blank=True)
    nickel = models.FloatField(_("nickel (mg/kg MS)"), null=True, blank=True)
    plomb = models.FloatField(_("plomb (mg/kg MS)"), null=True, blank=True)
    zinc_total = models.FloatField(_("zinc total (mg/kg MS)"), null=True, blank=True)
    arsenic = models.FloatField(_("arsenic total (mg/kg MS)"), null=True, blank=True)
    cobalt = models.FloatField(_("cobalt (mg/kg sec)"), null=True, blank=True)
    molybdene = models.FloatField(_("molybdène total (mg/kg sec)"), null=True, blank=True)
    selenium = models.FloatField(_("sélénium total (mg/kg sec)"), null=True, blank=True)
    fer_total = models.FloatField(_("fer total (% sec)"), null=True, blank=True)
    manganese_total = models.FloatField(_("manganèse total (mg/kg sec)"), null=True, blank=True)
    bore_total = models.FloatField(_("bore total (mg/kg sec)"), null=True, blank=True)
    aluminium_echangeable = models.FloatField(_("aluminium échangeable (mg/kg sec)"), null=True, blank=True)
    aluminium_total = models.FloatField(_("aluminium total (% sec)"), null=True, blank=True)

    # ── Contaminants organiques (annexe) : sommes conservées à l'identique (« <0.056 »…) ──
    somme_16_hap = models.CharField(_("somme 16 HAP (mg/kg MS)"), max_length=50, blank=True)
    somme_7_pcb = models.CharField(_("somme 7 PCB (mg/kg MS)"), max_length=50, blank=True)

    document = models.FileField(_("document"), upload_to=document_upload_path, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("analyse de sol")
        verbose_name_plural = _("analyses de sol")
        ordering = ("-date",)


class Laboratoire(models.Model):
    """Laboratoire d'analyse de sol partenaire, proposé lors d'une demande d'analyse.

    Les fiches sont saisies par un administrateur (pas de données inventées) et
    seuls les labos `actif=True` sont proposés à l'agriculteur.
    """

    nom = models.CharField(_("nom"), max_length=255)
    description = models.TextField(_("description"), blank=True)
    specialites = models.CharField(
        _("spécialités"), max_length=255, blank=True,
        help_text=_("ex : analyses physico-chimiques, reliquats azotés, oligo-éléments"),
    )
    region = models.CharField(_("région"), max_length=100, blank=True)
    email = models.EmailField(_("email"), blank=True)
    telephone = models.CharField(_("téléphone"), max_length=30, blank=True)
    site_web = models.URLField(_("site web"), blank=True)
    delai_jours = models.PositiveIntegerField(_("délai indicatif (jours)"), null=True, blank=True)
    actif = models.BooleanField(_("actif"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("laboratoire partenaire")
        verbose_name_plural = _("laboratoires partenaires")
        ordering = ("nom",)

    def __str__(self):
        return self.nom


class DemandeAnalyse(models.Model):
    """Demande d'analyse de sol adressée à un laboratoire partenaire, suivie par statut."""

    class Type(models.TextChoices):
        COMPLETE = "complete", _("Analyse complète (physico-chimique)")
        BASE = "base", _("Analyse de base (pH, MO, N-P-K)")
        RELIQUAT = "reliquat", _("Reliquat azoté")
        OLIGO = "oligo", _("Oligo-éléments")
        MATIERE_ORGANIQUE = "matiere_organique", _("Matière organique")
        AUTRE = "autre", _("Autre")

    class Statut(models.TextChoices):
        ENVOYEE = "envoyee", _("Envoyée")
        EN_COURS = "en_cours", _("En cours")
        RECUE = "recue", _("Reçue")
        ANNULEE = "annulee", _("Annulée")

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="demandes_analyse")
    parcelle = models.ForeignKey("parcelles.Parcelle", on_delete=models.CASCADE, related_name="demandes_analyse")
    laboratoire = models.ForeignKey(Laboratoire, on_delete=models.SET_NULL, null=True, blank=True, related_name="demandes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    type_analyse = models.CharField(_("type d'analyse"), max_length=20, choices=Type.choices, default=Type.COMPLETE)
    statut = models.CharField(_("statut"), max_length=10, choices=Statut.choices, default=Statut.ENVOYEE)
    message = models.TextField(_("message"), blank=True)
    # Résultat rattaché une fois l'analyse revenue du labo (relie la boucle demande → analyse).
    analyse = models.ForeignKey(AnalyseSol, on_delete=models.SET_NULL, null=True, blank=True, related_name="demande")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("demande d'analyse")
        verbose_name_plural = _("demandes d'analyse")
        ordering = ("-created_at",)

    def __str__(self):
        labo = self.laboratoire.nom if self.laboratoire else _("labo supprimé")
        return f"{self.parcelle} → {labo}"
