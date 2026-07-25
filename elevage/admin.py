from django.contrib import admin

from .models import Espece, Race


class RaceInline(admin.TabularInline):
    model = Race
    extra = 0
    fields = ("nom", "aptitude", "robe", "origine")
    show_change_link = True


@admin.register(Espece)
class EspeceAdmin(admin.ModelAdmin):
    list_display = ("nom", "famille", "production", "duree_gestation_jours")
    list_filter = ("famille", "production")
    search_fields = ("nom", "nom_scientifique")
    inlines = [RaceInline]


@admin.register(Race)
class RaceAdmin(admin.ModelAdmin):
    list_display = ("nom", "espece", "aptitude", "origine")
    list_filter = ("espece__famille",)
    search_fields = ("nom", "espece__nom", "origine")
