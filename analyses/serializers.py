from rest_framework import serializers

from .models import AnalysisResult, BiodiversiteFiche


class AnalysisResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalysisResult
        exclude = ["exploitation"]
        read_only_fields = ["id", "created_at", "status", "parsed_data"]


class BiodiversiteFicheSerializer(serializers.ModelSerializer):
    class Meta:
        model = BiodiversiteFiche
        exclude = ["exploitation"]
        read_only_fields = ["id", "created_at"]
