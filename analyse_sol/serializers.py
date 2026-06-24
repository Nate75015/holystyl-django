from rest_framework import serializers

from .models import AnalyseSol


class AnalyseSolSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyseSol
        exclude = ["exploitation"]
        read_only_fields = ["id", "created_at"]
