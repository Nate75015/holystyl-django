from django.contrib import admin

from .models import Article, Depot, Mouvement


class ArticleInline(admin.TabularInline):
    model = Article
    extra = 0
    fields = ("nom", "categorie", "quantite", "unite", "seuil_alerte")
    show_change_link = True


@admin.register(Depot)
class DepotAdmin(admin.ModelAdmin):
    list_display = ("nom", "exploitation", "type_depot", "localisation", "capacite")
    list_filter = ("type_depot",)
    search_fields = ("nom", "localisation")
    inlines = [ArticleInline]


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("nom", "exploitation", "categorie", "quantite", "unite", "seuil_alerte", "depot")
    list_filter = ("categorie", "unite", "depot")
    search_fields = ("nom", "reference", "fournisseur", "lot")
    # Le stock ne se corrige que par un mouvement : le rendre saisissable ici
    # rouvrirait la porte à un niveau que le journal n'explique pas.
    readonly_fields = ("quantite",)


@admin.register(Mouvement)
class MouvementAdmin(admin.ModelAdmin):
    list_display = ("date", "article", "type_mouvement", "motif", "quantite", "quantite_apres", "user")
    list_filter = ("type_mouvement", "motif")
    search_fields = ("article__nom", "notes")
    date_hierarchy = "date"
    readonly_fields = ("quantite_apres",)
