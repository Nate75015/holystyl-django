from django.contrib import admin

from .models import Connexion


@admin.register(Connexion)
class ConnexionAdmin(admin.ModelAdmin):
    list_display = ("demandeur", "destinataire", "statut", "created_at", "responded_at")
    list_filter = ("statut",)
    search_fields = ("demandeur__email", "destinataire__email")
