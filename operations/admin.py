from django.contrib import admin

from .models import AffectationEngin, CatalogueEngin, EntretienMateriel, Machine, MachineLog


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "brand", "status", "total_hours", "exploitation")
    list_filter = ("type", "status")
    search_fields = ("name", "brand", "model", "serial_number")


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
