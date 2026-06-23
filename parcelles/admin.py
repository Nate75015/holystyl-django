from django.contrib import admin

from .models import CropStage, Parcelle


class CropStageInline(admin.TabularInline):
    model = CropStage
    extra = 0


@admin.register(Parcelle)
class ParcelleAdmin(admin.ModelAdmin):
    list_display = ("name", "exploitation", "culture", "area", "irrigation_type", "status")
    list_filter = ("status", "irrigation_type", "culture")
    search_fields = ("name", "culture", "commune", "cadastral_ref")
    inlines = [CropStageInline]


@admin.register(CropStage)
class CropStageAdmin(admin.ModelAdmin):
    list_display = ("stage_name", "parcelle", "start_date", "end_date", "kc_value")
    search_fields = ("stage_name", "parcelle__name")
