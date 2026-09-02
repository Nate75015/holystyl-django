"""Planning des interventions, bons d'intervention et matériel.

Fidèle aux tables Drizzle : planning_tasks, planning_task_technicians,
planning_task_documents, planning_time_logs, planning_absences,
planning_category_colors, planning_access, intervention_reports,
equipment_catalog, task_equipment.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel

EXP = lambda related: dict(  # noqa: E731
    on_delete=models.CASCADE, related_name=related
)

TYPE_CHOICES = [
    ("irrigation", "Irrigation"), ("traitement", "Traitement"), ("fertilisation", "Fertilisation"),
    ("recolte", "Récolte"), ("semis", "Semis"), ("travail_sol", "Travail du sol"),
    ("taille", "Taille"), ("maintenance", "Maintenance"), ("observation", "Observation"),
    ("chantier", "Chantier"), ("depannage", "Dépannage"),
    ("rendez_vous", "Rendez-vous"), ("autre", "Autre"),
]


class PlanningTask(TimeStampedModel):
    class Statut(models.TextChoices):
        PLANIFIE = "planifie", _("Planifié")
        EN_COURS = "en_cours", _("En cours")
        EN_PAUSE = "en_pause", _("En pause")
        TERMINE = "termine", _("Terminé")
        ANNULE = "annule", _("Annulé")
        REPORTE = "reporte", _("Reporté")

    class Priorite(models.TextChoices):
        BASSE = "basse", _("Basse")
        NORMALE = "normale", _("Normale")
        HAUTE = "haute", _("Haute")
        URGENTE = "urgente", _("Urgente")

    class StatutFacturation(models.TextChoices):
        NON_APPLICABLE = "non_applicable", _("Non applicable")
        A_FACTURER = "a_facturer", _("À facturer")
        FACTURE = "facture", _("Facturé")
        AVOIR = "avoir", _("Avoir")

    exploitation = models.ForeignKey("exploitations.Exploitation", **EXP("planning_tasks"))
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="autre")
    titre = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    client_nom = models.CharField(max_length=255, blank=True)
    client_adresse = models.TextField(blank=True)
    client_telephone = models.CharField(max_length=50, blank=True)
    parcelle = models.ForeignKey("parcelles.Parcelle", on_delete=models.SET_NULL, null=True, blank=True)
    date_debut = models.DateTimeField(null=True, blank=True)
    date_fin = models.DateTimeField(null=True, blank=True)
    duree_estimee_minutes = models.IntegerField(default=60)
    journee_entiere = models.BooleanField(default=False)
    is_backlog = models.BooleanField(default=True)
    technicien = models.ForeignKey("equipe.TeamMember", on_delete=models.SET_NULL, null=True, blank=True, related_name="planning_tasks")
    technicien_nom = models.CharField(max_length=255, blank=True)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.PLANIFIE)
    statut_facturation = models.CharField(max_length=15, choices=StatutFacturation.choices, default=StatutFacturation.NON_APPLICABLE)
    completed_at = models.DateTimeField(null=True, blank=True)
    priorite = models.CharField(max_length=10, choices=Priorite.choices, default=Priorite.NORMALE)
    couleur = models.CharField(max_length=20, blank=True)
    categorie_intervention = models.CharField(max_length=30, default="autre")
    competences_requises = models.CharField(max_length=500, blank=True)
    zone_geographique = models.CharField(max_length=255, blank=True)
    temps_trajet_minutes = models.IntegerField(default=0)
    temps_prepa_minutes = models.IntegerField(default=0)
    temps_admin_minutes = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    consignes_terrain = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_by_name = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = _("tâche de planning")
        verbose_name_plural = _("tâches de planning")
        ordering = ("date_debut",)
        indexes = [
            models.Index(fields=["exploitation", "statut"]),
            models.Index(fields=["technicien", "date_debut"]),
        ]

    def __str__(self):
        return self.titre


class PlanningTaskTechnician(models.Model):
    task = models.ForeignKey(PlanningTask, on_delete=models.CASCADE, related_name="technicians")
    technicien = models.ForeignKey("equipe.TeamMember", on_delete=models.CASCADE)
    technicien_nom = models.CharField(max_length=255, blank=True)
    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("affectation technicien")
        verbose_name_plural = _("affectations techniciens")


class PlanningTaskDocument(models.Model):
    class Type(models.TextChoices):
        PHOTO = "photo", _("Photo")
        PLAN = "plan", _("Plan")
        SCHEMA = "schema", _("Schéma")
        DOCUMENT = "document", _("Document")
        AUTRE = "autre", _("Autre")

    task = models.ForeignKey(PlanningTask, on_delete=models.CASCADE, related_name="documents")
    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE)
    nom = models.CharField(max_length=255)
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.DOCUMENT)
    url = models.TextField()
    file_key = models.CharField(max_length=500, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    taille = models.IntegerField(null=True, blank=True)
    uploaded_by = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PlanningTimeLog(models.Model):
    class Action(models.TextChoices):
        START = "start", _("Démarrage")
        PAUSE = "pause", _("Pause")
        RESUME = "resume", _("Reprise")
        COMPLETE = "complete", _("Fin")

    task = models.ForeignKey(PlanningTask, on_delete=models.CASCADE, related_name="time_logs")
    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE)
    action = models.CharField(max_length=10, choices=Action.choices)
    timestamp = models.DateTimeField()
    technicien = models.ForeignKey("equipe.TeamMember", on_delete=models.SET_NULL, null=True, blank=True)
    technicien_nom = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("timestamp",)


class PlanningAbsence(TimeStampedModel):
    class Type(models.TextChoices):
        CONGE_PAYE = "conge_paye", _("Congé payé")
        RTT = "rtt", "RTT"
        MALADIE = "maladie", _("Maladie")
        FORMATION = "formation", _("Formation")
        SANS_SOLDE = "sans_solde", _("Sans solde")
        AUTRE = "autre", _("Autre")

    class DemiJournee(models.TextChoices):
        MATIN = "matin", _("Matin")
        APRES_MIDI = "apres_midi", _("Après-midi")
        JOURNEE = "journee", _("Journée")

    class Statut(models.TextChoices):
        DEMANDE = "demande", _("Demandé")
        APPROUVE = "approuve", _("Approuvé")
        REFUSE = "refuse", _("Refusé")

    exploitation = models.ForeignKey("exploitations.Exploitation", **EXP("absences"))
    technicien = models.ForeignKey("equipe.TeamMember", on_delete=models.CASCADE, related_name="absences")
    technicien_nom = models.CharField(max_length=255, blank=True)
    type = models.CharField(max_length=12, choices=Type.choices, default=Type.CONGE_PAYE)
    motif = models.CharField(max_length=500, blank=True)
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True)
    demi_journee_debut = models.CharField(max_length=10, choices=DemiJournee.choices, default=DemiJournee.JOURNEE)
    demi_journee_fin = models.CharField(max_length=10, choices=DemiJournee.choices, default=DemiJournee.JOURNEE)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.DEMANDE)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    approved_by_name = models.CharField(max_length=255, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("absence")
        verbose_name_plural = _("absences")
        ordering = ("-date_debut",)


class PlanningCategoryColor(models.Model):
    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="category_colors")
    category_key = models.CharField(max_length=100)
    category_label = models.CharField(max_length=255)
    couleur = models.CharField(max_length=20, default="#3B82F6")
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("sort_order",)


class PlanningAccess(models.Model):
    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="planning_access")
    technicien = models.ForeignKey("equipe.TeamMember", on_delete=models.CASCADE)
    can_view_planning = models.BooleanField(default=True)
    can_create_tasks = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class AccesPlanning(TimeStampedModel):
    """Qui peut ouvrir le planning d'une exploitation, et jusqu'où.

    Le chef d'exploitation n'y figure pas : le planning est le sien, il a tout
    par nature. Tous les autres — salariés compris — demandent l'accès, qu'il
    accorde à un niveau donné, comme on partage un agenda.

    `PlanningAccess`, juste au-dessus, visait la même chose mais s'indexait sur
    TeamMember : il ne pouvait pas représenter un bailleur ni un comptable, qui
    se rattachent par une fiche Partenaire. L'autorisation porte donc ici sur
    le compte lui-même, seul dénominateur commun à tous les rôles.
    """

    class Niveau(models.TextChoices):
        LECTURE = "lecture", _("Lecture")
        ECRITURE = "ecriture", _("Écriture")
        GESTION = "gestion", _("Gestion des accès")

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", _("En attente")
        ACCORDE = "accorde", _("Accordé")
        REFUSE = "refuse", _("Refusé")

    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE, related_name="acces_planning")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="acces_planning", verbose_name=_("compte"))
    niveau = models.CharField(_("niveau"), max_length=10,
                              choices=Niveau.choices, default=Niveau.LECTURE)
    statut = models.CharField(_("statut"), max_length=10,
                              choices=Statut.choices, default=Statut.EN_ATTENTE)
    #: Le mot que le demandeur joint à sa demande, s'il en met un.
    message = models.TextField(_("message"), blank=True)
    decide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="acces_planning_decides", verbose_name=_("décidé par"))
    decide_le = models.DateTimeField(_("décidé le"), null=True, blank=True)

    class Meta:
        verbose_name = _("accès au planning")
        verbose_name_plural = _("accès au planning")
        ordering = ("statut", "user_id")
        constraints = [
            models.UniqueConstraint(fields=["exploitation", "user"],
                                    name="un_seul_acces_planning_par_compte"),
        ]

    def __str__(self):
        return f"{self.user} — {self.get_niveau_display()} ({self.get_statut_display()})"


class EquipmentCatalog(TimeStampedModel):
    class Categorie(models.TextChoices):
        OUTIL_MAIN = "outil_main", _("Outil à main")
        OUTIL_COUPE = "outil_coupe", _("Outil de coupe")
        OUTIL_MOTORISE = "outil_motorise", _("Outil motorisé")
        ENGIN = "engin", _("Engin")
        PROTECTION = "protection", _("Protection")
        ARROSAGE = "arrosage", _("Arrosage")
        MESURE = "mesure", _("Mesure")
        TRANSPORT = "transport", _("Transport")
        AUTRE = "autre", _("Autre")

    class Etat(models.TextChoices):
        BON = "bon", _("Bon")
        MOYEN = "moyen", _("Moyen")
        A_REPARER = "a_reparer", _("À réparer")
        HORS_SERVICE = "hors_service", _("Hors service")

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="equipment_catalog")
    nom = models.CharField(max_length=255)
    categorie = models.CharField(max_length=15, choices=Categorie.choices, default=Categorie.AUTRE)
    description = models.TextField(blank=True)
    quantite_disponible = models.IntegerField(default=1)
    emplacement = models.CharField(max_length=255, blank=True)
    etat = models.CharField(max_length=15, choices=Etat.choices, default=Etat.BON)

    class Meta:
        verbose_name = _("matériel")
        verbose_name_plural = _("catalogue matériel")
        ordering = ("nom",)

    def __str__(self):
        return self.nom


class TaskEquipment(models.Model):
    planning_task = models.ForeignKey(PlanningTask, on_delete=models.CASCADE, related_name="equipment")
    equipment = models.ForeignKey(EquipmentCatalog, on_delete=models.SET_NULL, null=True, blank=True)
    nom = models.CharField(max_length=255)
    quantite = models.IntegerField(default=1)
    emplacement = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class InterventionReport(TimeStampedModel):
    """Bon d'intervention détaillé (signature, matériel, produits, photos)."""

    class EtatGeneral(models.TextChoices):
        BON = "bon", _("Bon")
        MOYEN = "moyen", _("Moyen")
        MAUVAIS = "mauvais", _("Mauvais")
        CRITIQUE = "critique", _("Critique")

    class Statut(models.TextChoices):
        BROUILLON = "brouillon", _("Brouillon")
        COMPLETE = "complete", _("Complété")
        VALIDE = "valide", _("Validé")
        ARCHIVE = "archive", _("Archivé")

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="intervention_reports")
    planning_task = models.ForeignKey(PlanningTask, on_delete=models.CASCADE, related_name="reports")
    intervention_type = models.CharField(max_length=100, blank=True)
    titre = models.CharField(max_length=255)
    client_nom = models.CharField(max_length=255, blank=True)
    client_adresse = models.TextField(blank=True)
    client_telephone = models.CharField(max_length=50, blank=True)
    parcelle_name = models.CharField(max_length=255, blank=True)
    technicien_nom = models.CharField(max_length=255, blank=True)
    technicien = models.ForeignKey("equipe.TeamMember", on_delete=models.SET_NULL, null=True, blank=True)
    date_intervention = models.DateField(null=True, blank=True)
    heure_debut = models.CharField(max_length=10, blank=True)
    heure_fin = models.CharField(max_length=10, blank=True)
    temps_pause_minutes = models.IntegerField(default=0)
    temps_trajet_minutes = models.IntegerField(default=0)
    description_travaux = models.TextField(blank=True)
    travaux_realises = models.JSONField(null=True, blank=True)
    materiel_utilise = models.JSONField(null=True, blank=True)
    produits_utilises = models.JSONField(null=True, blank=True)
    observations = models.TextField(blank=True)
    recommandations = models.TextField(blank=True)
    etat_general = models.CharField(max_length=10, choices=EtatGeneral.choices, blank=True)
    photo_avant_url = models.TextField(blank=True)
    photo_apres_url = models.TextField(blank=True)
    photos_supplementaires = models.JSONField(null=True, blank=True)
    signature_client_url = models.TextField(blank=True)
    signature_client_nom = models.CharField(max_length=255, blank=True)
    signature_tech_url = models.TextField(blank=True)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.BROUILLON)

    class Meta:
        verbose_name = _("bon d'intervention")
        verbose_name_plural = _("bons d'intervention")
        ordering = ("-created_at",)

    def __str__(self):
        return f"Bon — {self.titre}"
