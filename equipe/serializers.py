from rest_framework import serializers

from .models import Task, TeamMember


class TeamMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamMember
        exclude = ["exploitation", "password_hash", "location_token", "location_token_expires_at"]
        read_only_fields = ["id", "is_online", "last_seen_at", "created_at", "updated_at"]


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        exclude = ["exploitation"]
        read_only_fields = ["id", "created_at", "updated_at",
                            "reminder_sent_24h", "reminder_sent_1h", "sms_sent_24h", "sms_sent_1h"]
