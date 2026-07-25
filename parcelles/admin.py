from django.contrib import admin

from .models import CropStage, Parcelle, ParcelleCampagne


class CampagneInline(admin.TabularInline):
    model = ParcelleCampagne
    extra = 0
    fields = ("libelle", "culture", "variety", "irrigation_type")
    show_change_link = True


class CropStageInline(admin.TabularInline):
    model = CropStage
    extra = 0


@admin.register(Parcelle)
class ParcelleAdmin(admin.ModelAdmin):
    list_display = ("name", "exploitation", "area", "status")
    list_filter = ("status",)
    search_fields = ("name", "commune", "cadastral_ref")
    inlines = [CampagneInline]


@admin.register(ParcelleCampagne)
class ParcelleCampagneAdmin(admin.ModelAdmin):
    list_display = ("parcelle", "libelle", "culture", "variety", "irrigation_type")
    list_filter = ("libelle", "irrigation_type", "culture")
    search_fields = ("parcelle__name", "culture", "variety")
    inlines = [CropStageInline]


@admin.register(CropStage)
class CropStageAdmin(admin.ModelAdmin):
    list_display = ("stage_name", "parcelle_campagne", "start_date", "end_date", "kc_value")
    search_fields = ("stage_name", "parcelle_campagne__parcelle__name")
