from django.contrib import admin

from .models import Email


@admin.register(Email)
class EmailAdmin(admin.ModelAdmin):
    list_display = ("id", "subject", "to", "sender", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("subject", "to", "body")
    readonly_fields = ("created_at", "updated_at")
