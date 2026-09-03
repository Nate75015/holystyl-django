from django.contrib import admin

from .models import ActeNotarie, Assurance, Bail, Contrat, Msa


@admin.register(Contrat)
class ContratAdmin(admin.ModelAdmin):
    list_display = ("intitule", "type_contrat", "contractant", "date_debut", "date_fin", "statut", "exploitation")
    list_filter = ("type_contrat", "statut")
    search_fields = ("intitule", "contractant")


@admin.register(Bail)
class BailAdmin(admin.ModelAdmin):
    list_display = ("designation", "bailleur", "preneur", "surface_ha", "loyer_annuel", "date_debut", "date_fin", "statut", "exploitation")
    list_filter = ("statut",)
    search_fields = ("designation", "bailleur", "preneur")


@admin.register(ActeNotarie)
class ActeNotarieAdmin(admin.ModelAdmin):
    list_display = ("objet", "type_acte", "statut", "notaire", "date_signature", "montant", "exploitation")
    list_filter = ("type_acte", "statut")
    search_fields = ("objet", "notaire", "parties", "reference")


@admin.register(Assurance)
class AssuranceAdmin(admin.ModelAdmin):
    list_display = ("intitule", "type_assurance", "assureur", "numero_police", "prime_annuelle", "date_fin", "statut", "exploitation")
    list_filter = ("type_assurance", "statut")
    search_fields = ("intitule", "assureur", "numero_police")


@admin.register(Msa)
class MsaAdmin(admin.ModelAdmin):
    list_display = ("intitule", "type_cotisation", "numero_adherent", "montant", "date_echeance", "statut", "exploitation")
    list_filter = ("type_cotisation", "statut")
    search_fields = ("intitule", "numero_adherent", "caisse")
