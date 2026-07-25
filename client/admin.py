from django.contrib import admin

from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("nom", "type_client", "statut", "ville", "email", "telephone", "ca_annuel", "exploitation")
    list_filter = ("type_client", "statut")
    search_fields = ("nom", "contact_principal", "email", "ville", "siret")
