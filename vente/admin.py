from django.contrib import admin

from .models import Boutique, Commande, LigneCommande, Produit


@admin.register(Boutique)
class BoutiqueAdmin(admin.ModelAdmin):
    list_display = ("nom", "slug", "est_ouverte", "visible_marche", "localite")
    list_filter = ("est_ouverte", "visible_marche", "retrait_ferme", "livraison")
    search_fields = ("titre", "slug", "exploitation__name")
    prepopulated_fields = {"slug": ("titre",)}


@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    list_display = ("nom", "exploitation", "categorie", "prix_ttc", "unite_vente", "statut", "article")
    list_filter = ("statut", "categorie", "visible_marche")
    search_fields = ("nom", "description", "exploitation__name")


class LigneInline(admin.TabularInline):
    model = LigneCommande
    extra = 0
    fields = ("libelle", "quantite", "unite_libelle", "prix_unitaire_ttc", "quantite_stock", "article")
    readonly_fields = ("quantite_stock",)


@admin.register(Commande)
class CommandeAdmin(admin.ModelAdmin):
    list_display = ("numero", "exploitation", "acheteur_nom", "statut", "montant_ttc", "date_souhaitee")
    list_filter = ("statut", "mode_retrait")
    search_fields = ("numero", "acheteur_nom", "acheteur_email")
    date_hierarchy = "created_at"
    inlines = [LigneInline]
    # Les montants se recalculent depuis les lignes : les saisir à la main
    # ferait diverger la commande de ce qu'elle contient.
    readonly_fields = ("numero", "jeton", "montant_ht", "montant_tva", "montant_ttc")
