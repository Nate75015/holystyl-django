from django.contrib import admin

from .models import AiConversation, DailyReport, VocalDictionary


@admin.register(AiConversation)
class AiConversationAdmin(admin.ModelAdmin):
    list_display = ("exploitation", "role", "created_at")
    list_filter = ("role",)


@admin.register(DailyReport)
class DailyReportAdmin(admin.ModelAdmin):
    list_display = ("exploitation", "report_date", "dti_score", "kwh_per_m3", "alerts_count")
    list_filter = ("dti_score",)


@admin.register(VocalDictionary)
class VocalDictionaryAdmin(admin.ModelAdmin):
    list_display = ("term", "replacement", "category", "exploitation")
    list_filter = ("category",)
