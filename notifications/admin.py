from django.contrib import admin

from .models import Notification, NotificationRule


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "type", "priority", "read", "created_at")
    list_filter = ("type", "priority", "read")
    search_fields = ("title", "message")


@admin.register(NotificationRule)
class NotificationRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "type", "condition_type", "enabled")
    list_filter = ("enabled", "type")
