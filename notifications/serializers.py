from rest_framework import serializers

from .models import Notification, NotificationRule


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        exclude = ["user"]
        read_only_fields = ["id", "created_at"]


class NotificationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationRule
        exclude = ["user"]
        read_only_fields = ["id", "created_at", "updated_at"]
