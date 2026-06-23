from django.contrib import admin

from .models import Task, TaskReminder, TeamMember


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ("name", "role", "exploitation", "phone", "is_active", "is_online")
    list_filter = ("role", "is_active")
    search_fields = ("name", "email", "phone")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "exploitation", "assigned_to", "status", "priority", "due_date")
    list_filter = ("status", "priority")
    search_fields = ("title",)


@admin.register(TaskReminder)
class TaskReminderAdmin(admin.ModelAdmin):
    list_display = ("task", "type", "scheduled_at", "status", "sent_at")
    list_filter = ("type", "status")
