from django.contrib import admin

from .models import AnalysisResult, BiodiversiteFiche


@admin.register(AnalysisResult)
class AnalysisResultAdmin(admin.ModelAdmin):
    list_display = ("__str__", "analysis_type", "lab_name", "sample_date", "status", "ph")
    list_filter = ("analysis_type", "status")


@admin.register(BiodiversiteFiche)
class BiodiversiteFicheAdmin(admin.ModelAdmin):
    list_display = ("parcelle", "date", "score", "nb_especes_vegetales", "nb_especes_animales")
