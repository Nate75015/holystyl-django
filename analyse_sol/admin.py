from django.contrib import admin

from .models import AnalyseSol


@admin.register(AnalyseSol)
class AnalyseSolAdmin(admin.ModelAdmin):
    list_display = ("parcelle", "date", "ph", "matiere_organique", "laboratoire")
