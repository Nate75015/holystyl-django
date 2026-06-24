from django.contrib import admin

from .models import AidePAC


@admin.register(AidePAC)
class AidePACAdmin(admin.ModelAdmin):
    list_display = ("campagne", "categorie", "libelle", "montant", "statut", "exploitation")
    list_filter = ("campagne", "categorie", "statut")
    search_fields = ("libelle",)
