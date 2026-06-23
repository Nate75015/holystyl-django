from django.contrib import admin

from .models import Conversation, ConversationMember, Message, PieceJointe


class PieceJointeInline(admin.TabularInline):
    model = PieceJointe
    extra = 0


class MemberInline(admin.TabularInline):
    model = ConversationMember
    extra = 0


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "__str__", "is_group", "created_by", "updated_at")
    list_filter = ("is_group",)
    inlines = [MemberInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "created_at")
    list_filter = ("conversation",)
    search_fields = ("body",)
    inlines = [PieceJointeInline]
