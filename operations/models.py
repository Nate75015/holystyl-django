"""Opérations & matériel : machines, logs, interventions, entretiens, affectations, catalogue.

Fidèle aux tables Drizzle `machines`, `machine_logs`, `interventions`,
`entretiens_materiel`, `affectations_engins`, `catalogue_engins`.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel

from .materiel import CHOIX_GROUPES, LONGUEUR_MAX_TYPE, Famille, TypeMateriel, est_automoteur, famille_de


class Machine(TimeStampedModel):
    """Un engin que possède l'exploitation, du tracteur à la pince à balles.

    Le type vient de `operations.materiel`, partagé avec `CatalogueEngin` : les
    deux désignent le même monde, ils ne peuvent pas le nommer différemment.
    """

    #: Conservé pour que `Machine.Type` reste une porte d'entrée lisible.
    Type = TypeMateriel

    class Detention(models.TextChoices):
        """À qui appartient l'engin, et à quel titre.

        Un booléen « en CUMA » aurait répondu à la question du jour sans dire
        de quelle CUMA il s'agit, et il aurait fallu le remplacer dès la
        première machine en copropriété ou en location — deux situations
        courantes. La question « est-ce à la CUMA ? » se lit ici aussi bien.
        """

        PROPRE = "propre", _("En propre")
        CUMA = "cuma", _("En CUMA")
        COPROPRIETE = "copropriete", _("En copropriété")
        LOCATION = "location", _("En location")
        ETA = "eta", _("Confié à une ETA")

    class Status(models.TextChoices):
        OPERATIONAL = "operational", _("Opérationnelle")
        MAINTENANCE = "maintenance", _("Maintenance")
        BROKEN = "broken", _("En panne")
        RETIRED = "retired", _("Réformée")

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="machines")
    name = models.CharField(_("nom"), max_length=255)
    type = models.CharField(_("type"), max_length=LONGUEUR_MAX_TYPE, choices=CHOIX_GROUPES)
    brand = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    total_hours = models.FloatField(default=0)
    last_maintenance_date = models.DateField(null=True, blank=True)
    next_maintenance_hours = models.FloatField(null=True, blank=True)
    next_maintenance_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPERATIONAL)
    detention = models.CharField(
        _("détention"), max_length=15, choices=Detention.choices, default=Detention.PROPRE)
    proprietaire = models.ForeignKey(
        "client.Partenaire", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="materiels", verbose_name=_("propriétaire"),
        help_text=_("La CUMA, le loueur ou l'ETA à qui appartient l'engin. "
                    "Vide quand il est à l'exploitation."))
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("machine")
        verbose_name_plural = _("machines")
        ordering = ("name",)
        indexes = [
            models.Index(fields=["exploitation", "type"]),
            models.Index(fields=["exploitation", "detention"]),
        ]

    def __str__(self):
        return self.name

    @property
    def famille(self):
        """La famille du type, déduite plutôt que stockée : pas de dérive possible."""
        return famille_de(self.type)

    @property
    def famille_libelle(self):
        return Famille(self.famille).label

    @property
    def est_en_cuma(self):
        """L'engin appartient-il à une CUMA ? La question posée, telle quelle."""
        return self.detention == self.Detention.CUMA

    @property
    def est_automoteur(self):
        """Vrai pour un engin qui roule seul — heures, carburant, carte grise."""
        return est_automoteur(self.type)


class MachineLog(models.Model):
    class LogType(models.TextChoices):
        USAGE = "usage", _("Utilisation")
        MAINTENANCE = "maintenance", _("Maintenance")
        REPAIR = "repair", _("Réparation")
        INSPECTION = "inspection", _("Inspection")

    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="logs")
    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE)
    log_type = models.CharField(max_length=12, choices=LogType.choices)
    log_date = models.DateTimeField()
    hours_added = models.FloatField(null=True, blank=True)
    total_hours_after = models.FloatField(null=True, blank=True)
    description = models.TextField(blank=True)
    cost = models.FloatField(null=True, blank=True)
    technician_name = models.CharField(max_length=255, blank=True)
    parts_replaced = models.JSONField(null=True, blank=True)
    next_maintenance_hours = models.FloatField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-log_date",)


class EntretienMateriel(models.Model):
    class Type(models.TextChoices):
        VIDANGE = "vidange", _("Vidange")
        FILTRES = "filtres", _("Filtres")
        COURROIES = "courroies", _("Courroies")
        PNEUMATIQUES = "pneumatiques", _("Pneumatiques")
        FREINS = "freins", _("Freins")
        REVISION = "revision_complete", _("Révision complète")
        REPARATION = "reparation", _("Réparation")
        CONTROLE = "controle_technique", _("Contrôle technique")
        AUTRE = "autre", _("Autre")

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="entretiens")
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="entretiens")
    type = models.CharField(max_length=20, choices=Type.choices)
    date = models.DateTimeField()
    heures_compteur = models.FloatField(null=True, blank=True)
    km_compteur = models.FloatField(null=True, blank=True)
    cout = models.FloatField(default=0)
    description = models.TextField(blank=True)
    technicien = models.CharField(max_length=255, blank=True)
    pieces_remplacees = models.JSONField(null=True, blank=True)
    prochain_entretien_h = models.FloatField(null=True, blank=True)
    prochain_entretien_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("entretien")
        verbose_name_plural = _("entretiens")
        ordering = ("-date",)


class AffectationEngin(models.Model):
    class Operation(models.TextChoices):
        LABOUR = "labour", _("Labour")
        SEMIS = "semis", _("Semis")
        TRAITEMENT = "traitement", _("Traitement")
        RECOLTE = "recolte", _("Récolte")
        FERTILISATION = "fertilisation", _("Fertilisation")
        IRRIGATION = "irrigation", _("Irrigation")
        TRANSPORT = "transport", _("Transport")
        AUTRE = "autre", _("Autre")

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="affectations")
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="affectations")
    parcelle = models.ForeignKey("parcelles.Parcelle", on_delete=models.CASCADE)
    operation = models.CharField(max_length=15, choices=Operation.choices)
    date_debut = models.DateTimeField()
    date_fin = models.DateTimeField(null=True, blank=True)
    heures_utilisees = models.FloatField(null=True, blank=True)
    surface_ha = models.FloatField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("affectation d'engin")
        verbose_name_plural = _("affectations d'engins")
        ordering = ("-date_debut",)


class CatalogueEngin(models.Model):
    """Référentiel global de modèles d'engins (pas de FK exploitation)."""

    #: Le même vocabulaire que `Machine` : un semoir monograine s'appelle
    #: pareil qu'on décrive le modèle du marché ou l'exemplaire de la ferme.
    Type = TypeMateriel

    marque = models.CharField(max_length=100)
    modele = models.CharField(max_length=255)
    type = models.CharField(_("type"), max_length=LONGUEUR_MAX_TYPE, choices=CHOIX_GROUPES)
    puissance_cv = models.IntegerField(null=True, blank=True)
    largeur_travail_m = models.FloatField(null=True, blank=True)
    capacite_l = models.FloatField(null=True, blank=True)
    poids_kg = models.IntegerField(null=True, blank=True)
    annee_debut = models.IntegerField(null=True, blank=True)
    annee_fin = models.IntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    intervalle_entretien_h = models.IntegerField(default=500)
    intervalle_entretien_km = models.IntegerField(null=True, blank=True)
    image_url = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("modèle d'engin (catalogue)")
        verbose_name_plural = _("catalogue d'engins")
        ordering = ("marque", "modele")

    def __str__(self):
        return f"{self.marque} {self.modele}"
