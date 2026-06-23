"""Opérations & matériel : machines, logs, interventions, entretiens, affectations, catalogue.

Fidèle aux tables Drizzle `machines`, `machine_logs`, `interventions`,
`entretiens_materiel`, `affectations_engins`, `catalogue_engins`.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


class Machine(TimeStampedModel):
    class Type(models.TextChoices):
        PUMP = "pump", _("Pompe")
        TRACTOR = "tractor", _("Tracteur")
        ENROULEUR = "enrouleur", _("Enrouleur")
        PIVOT = "pivot", _("Pivot")
        SPRAYER = "sprayer", _("Pulvérisateur")
        OTHER = "other", _("Autre")

    class Status(models.TextChoices):
        OPERATIONAL = "operational", _("Opérationnelle")
        MAINTENANCE = "maintenance", _("Maintenance")
        BROKEN = "broken", _("En panne")
        RETIRED = "retired", _("Réformée")

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="machines")
    name = models.CharField(_("nom"), max_length=255)
    type = models.CharField(max_length=12, choices=Type.choices)
    brand = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    total_hours = models.FloatField(default=0)
    last_maintenance_date = models.DateField(null=True, blank=True)
    next_maintenance_hours = models.FloatField(null=True, blank=True)
    next_maintenance_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPERATIONAL)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("machine")
        verbose_name_plural = _("machines")
        ordering = ("name",)

    def __str__(self):
        return self.name


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


class Intervention(TimeStampedModel):
    class Type(models.TextChoices):
        IRRIGATION = "irrigation", _("Irrigation")
        TRAITEMENT = "traitement", _("Traitement")
        FERTILISATION = "fertilisation", _("Fertilisation")
        RECOLTE = "recolte", _("Récolte")
        SEMIS = "semis", _("Semis")
        TRAVAIL_SOL = "travail_sol", _("Travail du sol")
        TAILLE = "taille", _("Taille")
        PALISSAGE = "palissage", _("Palissage")
        DESHERBAGE = "desherbage", _("Désherbage")
        ECLAIRCISSAGE = "eclaircissage", _("Éclaircissage")
        EFFEUILLAGE = "effeuillage", _("Effeuillage")
        VENDANGE = "vendange", _("Vendange")
        MAINTENANCE = "maintenance", _("Maintenance")
        OBSERVATION = "observation", _("Observation")
        AUTRE = "autre", _("Autre")

    class Status(models.TextChoices):
        PLANIFIEE = "planifiee", _("Planifiée")
        EN_COURS = "en_cours", _("En cours")
        TERMINEE = "terminee", _("Terminée")
        ANNULEE = "annulee", _("Annulée")

    class Source(models.TextChoices):
        VOICE = "voice", _("Vocal")
        MANUAL = "manual", _("Manuel")
        AI = "ai", _("IA")

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="interventions")
    parcelle = models.ForeignKey("parcelles.Parcelle", on_delete=models.SET_NULL, null=True, blank=True)
    machine = models.ForeignKey(Machine, on_delete=models.SET_NULL, null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    assigned_to = models.ForeignKey("equipe.TeamMember", on_delete=models.SET_NULL, null=True, blank=True)
    task = models.ForeignKey("equipe.Task", on_delete=models.SET_NULL, null=True, blank=True)
    intervention_type = models.CharField(max_length=15, choices=Type.choices)
    title = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PLANIFIEE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    duration_hours = models.FloatField(null=True, blank=True)
    product = models.CharField(max_length=255, blank=True)
    dose = models.CharField(max_length=100, blank=True)
    unit = models.CharField(max_length=50, blank=True)
    surface = models.FloatField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    notes = models.TextField(blank=True)
    voice_transcript = models.TextField(blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MANUAL)

    class Meta:
        verbose_name = _("intervention")
        verbose_name_plural = _("interventions")
        ordering = ("-start_time",)
        indexes = [models.Index(fields=["exploitation", "-start_time"])]

    def __str__(self):
        return self.title or self.get_intervention_type_display()


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

    class Type(models.TextChoices):
        TRACTEUR = "tracteur", _("Tracteur")
        PULVERISATEUR = "pulverisateur", _("Pulvérisateur")
        SEMOIR = "semoir", _("Semoir")
        EPANDEUR = "epandeur", _("Épandeur")
        MOISSONNEUSE = "moissonneuse", _("Moissonneuse")
        CHARRUE = "charrue", _("Charrue")
        CULTIVATEUR = "cultivateur", _("Cultivateur")
        BENNE = "benne", _("Benne")
        POMPE = "pompe", _("Pompe")
        AUTRE = "autre", _("Autre")

    marque = models.CharField(max_length=100)
    modele = models.CharField(max_length=255)
    type = models.CharField(max_length=15, choices=Type.choices)
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
