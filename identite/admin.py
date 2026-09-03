from django.contrib import admin

from .models import Piece


@admin.register(Piece)
class PieceAdmin(admin.ModelAdmin):
    list_display = ("type_piece", "titulaire", "numero", "expire_le", "exploitation")
    list_filter = ("type_piece",)
    search_fields = ("titulaire", "numero")
