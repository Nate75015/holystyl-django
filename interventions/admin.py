from django.contrib import admin

from .models import Intervention


@admin.register(Intervention)
class InterventionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "intervention_type", "status", "parcelle", "start_time", "source")
    list_filter = ("intervention_type", "status", "source")
