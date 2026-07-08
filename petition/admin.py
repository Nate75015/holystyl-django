from django.contrib import admin

from .models import Petition, Signature


class SignatureInline(admin.TabularInline):
    model = Signature
    extra = 0
    readonly_fields = ("user", "comment", "created_at")


@admin.register(Petition)
class PetitionAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "created_by", "goal", "closed", "created_at")
    list_filter = ("closed",)
    search_fields = ("title", "description")
    inlines = [SignatureInline]


@admin.register(Signature)
class SignatureAdmin(admin.ModelAdmin):
    list_display = ("id", "petition", "user", "created_at")
    search_fields = ("petition__title", "user__email")
