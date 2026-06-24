from rest_framework import serializers

from .models import AffectationEngin, CatalogueEngin, EntretienMateriel, Machine, MachineLog


class _TenantSerializer(serializers.ModelSerializer):
    class Meta:
        exclude = ["exploitation"]
        read_only_fields = ["id", "created_at", "updated_at"]


class MachineSerializer(_TenantSerializer):
    class Meta(_TenantSerializer.Meta):
        model = Machine


class MachineLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = MachineLog
        exclude = ["exploitation"]
        read_only_fields = ["id", "created_at"]


class EntretienMaterielSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntretienMateriel
        exclude = ["exploitation"]
        read_only_fields = ["id", "created_at"]


class AffectationEnginSerializer(serializers.ModelSerializer):
    class Meta:
        model = AffectationEngin
        exclude = ["exploitation"]
        read_only_fields = ["id", "created_at"]


class CatalogueEnginSerializer(serializers.ModelSerializer):
    class Meta:
        model = CatalogueEngin
        fields = "__all__"
