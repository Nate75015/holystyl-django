from django.contrib import admin

from .models import CultureKc, Fertigation, Saison, TypeSol, Variete

admin.site.register(Fertigation)


class VarieteInline(admin.TabularInline):
    model = Variete
    extra = 0
    fields = ("nom", "couleur", "type_croissance", "note")


@admin.register(CultureKc)
class CultureKcAdmin(admin.ModelAdmin):
    list_display = ("nom", "categorie", "kc_initial", "kc_mid", "kc_end", "source")
    list_filter = ("categorie", "source")
    search_fields = ("nom", "nom_scientifique")
    inlines = [VarieteInline]


@admin.register(Variete)
class VarieteAdmin(admin.ModelAdmin):
    list_display = ("nom", "culture", "couleur", "type_croissance", "note")
    list_filter = ("culture__categorie",)
    search_fields = ("nom", "culture__nom")


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
