from django.contrib import admin

from .models import (
    EquipmentCatalog,
    InterventionReport,
    PlanningAbsence,
    PlanningAccess,
    PlanningCategoryColor,
    PlanningTask,
    PlanningTaskDocument,
    PlanningTaskTechnician,
    PlanningTimeLog,
    TaskEquipment,
)


@admin.register(PlanningTask)
class PlanningTaskAdmin(admin.ModelAdmin):
    list_display = ("titre", "exploitation", "type", "statut", "priorite", "technicien", "date_debut")
    list_filter = ("statut", "type", "priorite", "is_backlog")
    search_fields = ("titre", "client_nom")


@admin.register(InterventionReport)
class InterventionReportAdmin(admin.ModelAdmin):
    list_display = ("titre", "exploitation", "technicien_nom", "date_intervention", "statut")
    list_filter = ("statut", "etat_general")


@admin.register(EquipmentCatalog)
class EquipmentCatalogAdmin(admin.ModelAdmin):
    list_display = ("nom", "categorie", "etat", "quantite_disponible", "exploitation")
    list_filter = ("categorie", "etat")


admin.site.register([
    PlanningTaskTechnician, PlanningTaskDocument, PlanningTimeLog,
    PlanningAbsence, PlanningCategoryColor, PlanningAccess, TaskEquipment,
])
