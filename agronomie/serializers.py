from rest_framework import serializers

from .models import CultureKc, Fertigation, TypeSol


class FertigationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fertigation
        exclude = ["exploitation"]
        read_only_fields = ["id", "created_at"]


class CultureKcSerializer(serializers.ModelSerializer):
    class Meta:
        model = CultureKc
        fields = "__all__"


class TypeSolSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeSol
        fields = "__all__"
