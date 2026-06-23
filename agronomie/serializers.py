from rest_framework import serializers

from .models import CultureKc, Saison, TypeSol


class CultureKcSerializer(serializers.ModelSerializer):
    class Meta:
        model = CultureKc
        fields = "__all__"


class TypeSolSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeSol
        fields = "__all__"


class SaisonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Saison
        exclude = ["exploitation"]
        read_only_fields = ["id", "created_at", "updated_at"]
