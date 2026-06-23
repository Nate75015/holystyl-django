from rest_framework import serializers

from .models import AnalyseSol, AnalysisResult, BiodiversiteFiche


class AnalysisResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalysisResult
        exclude = ["exploitation"]
        read_only_fields = ["id", "created_at", "status", "parsed_data"]


class AnalyseSolSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyseSol
        exclude = ["exploitation"]
        read_only_fields = ["id", "created_at"]


class BiodiversiteFicheSerializer(serializers.ModelSerializer):
    class Meta:
        model = BiodiversiteFiche
        exclude = ["exploitation"]
        read_only_fields = ["id", "created_at"]
