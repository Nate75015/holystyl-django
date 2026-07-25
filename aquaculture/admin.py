from django.contrib import admin

from .models import Bassin, EspeceAquacole, Lot, Souche


class LotInline(admin.TabularInline):
    model = Lot
    extra = 0


@admin.register(Bassin)
class BassinAdmin(admin.ModelAdmin):
    list_display = ("nom", "type_bassin", "statut", "source_eau", "volume_m3", "exploitation")
    list_filter = ("type_bassin", "statut", "source_eau")
    search_fields = ("nom",)
    inlines = [LotInline]


@admin.register(Lot)
class LotAdmin(admin.ModelAdmin):
    list_display = ("espece", "souche", "bassin", "effectif", "poids_moyen_g", "statut", "date_mise_en_charge")
    list_filter = ("statut",)
    search_fields = ("espece", "souche", "bassin__nom")


class SoucheInline(admin.TabularInline):
    model = Souche
    extra = 0


@admin.register(EspeceAquacole)
class EspeceAquacoleAdmin(admin.ModelAdmin):
    list_display = ("nom", "nom_scientifique", "famille", "milieu", "production", "duree_cycle_jours")
    list_filter = ("famille", "milieu", "production")
    search_fields = ("nom", "nom_scientifique")
    inlines = [SoucheInline]


@admin.register(Souche)
class SoucheAdmin(admin.ModelAdmin):
    list_display = ("nom", "espece", "aptitude", "croissance", "note")
    list_filter = ("espece__famille",)
    search_fields = ("nom", "nom_scientifique", "espece__nom")
