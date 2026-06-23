from django.contrib import admin

from .models import Choix, Sondage, Vote


class ChoixInline(admin.TabularInline):
    model = Choix
    extra = 2


@admin.register(Sondage)
class SondageAdmin(admin.ModelAdmin):
    list_display = ("id", "question", "created_by", "closed", "created_at")
    list_filter = ("closed",)
    search_fields = ("question",)
    inlines = [ChoixInline]


admin.site.register(Vote)
