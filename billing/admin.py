from django.contrib import admin

from .models import ActivationCode, Subscription


@admin.register(ActivationCode)
class ActivationCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "email", "status", "used_at", "created_at")
    list_filter = ("status",)
    search_fields = ("code", "email")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("exploitation", "status", "current_period_end", "cancel_at_period_end")
    list_filter = ("status",)
