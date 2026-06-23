from django.contrib import admin

from .models import AffectationEngin, CatalogueEngin, EntretienMateriel, Intervention, Machine, MachineLog


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "brand", "status", "total_hours", "exploitation")
    list_filter = ("type", "status")
    search_fields = ("name", "brand", "model", "serial_number")


@admin.register(Intervention)
class InterventionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "intervention_type", "status", "parcelle", "start_time", "source")
    list_filter = ("intervention_type", "status", "source")


@admin.register(EntretienMateriel)
class EntretienMaterielAdmin(admin.ModelAdmin):
    list_display = ("machine", "type", "date", "cout", "technicien")
    list_filter = ("type",)


@admin.register(CatalogueEngin)
class CatalogueEnginAdmin(admin.ModelAdmin):
    list_display = ("marque", "modele", "type", "puissance_cv")
    list_filter = ("type", "marque")
    search_fields = ("marque", "modele")


admin.site.register([MachineLog, AffectationEngin])
