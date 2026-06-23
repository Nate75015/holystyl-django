from django.contrib import admin

from .models import SmtpConfig


@admin.register(SmtpConfig)
class SmtpConfigAdmin(admin.ModelAdmin):
    list_display = ("exploitation", "host", "port", "from_email", "enabled", "last_test_status")
    list_filter = ("enabled", "last_test_status")
