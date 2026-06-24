from rest_framework import serializers

from .models import Intervention


class InterventionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Intervention
        exclude = ["exploitation"]
        read_only_fields = ["id", "created_at", "updated_at", "user"]
