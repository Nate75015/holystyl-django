from django.contrib import admin

from .models import CultureKc, Fertigation, Saison, TypeSol

admin.site.register(Fertigation)


@admin.register(CultureKc)
class CultureKcAdmin(admin.ModelAdmin):
    list_display = ("nom", "categorie", "kc_initial", "kc_mid", "kc_end", "source")
    list_filter = ("categorie", "source")
    search_fields = ("nom", "nom_scientifique")


@admin.register(TypeSol)
class TypeSolAdmin(admin.ModelAdmin):
    list_display = ("nom", "texture", "capacite_retention_mm", "ph_typique")
    list_filter = ("texture",)
    search_fields = ("nom",)


@admin.register(Saison)
class SaisonAdmin(admin.ModelAdmin):
    list_display = ("nom", "exploitation", "date_debut", "date_fin", "active")
    list_filter = ("active",)
    search_fields = ("nom",)
