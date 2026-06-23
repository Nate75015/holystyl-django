from django.contrib import admin

from .models import LeadCapture


@admin.register(LeadCapture)
class LeadCaptureAdmin(admin.ModelAdmin):
    list_display = ("email", "source", "guide_sent_at", "created_at")
    list_filter = ("source",)
    search_fields = ("email",)
