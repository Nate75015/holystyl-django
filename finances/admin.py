from django.contrib import admin

from .models import Charge, Facture, FactureClient, Recolte, Revenu, SubventionExport


@admin.register(Charge)
class ChargeAdmin(admin.ModelAdmin):
    list_display = ("date", "categorie", "montant", "fournisseur", "exploitation")
    list_filter = ("categorie",)


@admin.register(Revenu)
class RevenuAdmin(admin.ModelAdmin):
    list_display = ("date", "categorie", "montant", "acheteur", "exploitation")
    list_filter = ("categorie",)


@admin.register(Facture)
class FactureAdmin(admin.ModelAdmin):
    list_display = ("numero", "client_nom", "date_emission", "montant_ttc", "statut")
    list_filter = ("statut",)
    search_fields = ("numero", "client_nom")


admin.site.register([Recolte, FactureClient, SubventionExport])
