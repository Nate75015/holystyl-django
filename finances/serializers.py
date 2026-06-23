from rest_framework import serializers

from .models import Charge, Facture, FactureClient, Recolte, Revenu, SubventionExport


class _TenantSerializer(serializers.ModelSerializer):
    class Meta:
        exclude = ["exploitation"]
        read_only_fields = ["id", "created_at"]


class ChargeSerializer(_TenantSerializer):
    class Meta(_TenantSerializer.Meta):
        model = Charge


class RevenuSerializer(_TenantSerializer):
    class Meta(_TenantSerializer.Meta):
        model = Revenu


class RecolteSerializer(_TenantSerializer):
    class Meta(_TenantSerializer.Meta):
        model = Recolte


class FactureClientSerializer(_TenantSerializer):
    class Meta(_TenantSerializer.Meta):
        model = FactureClient


class FactureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Facture
        exclude = ["exploitation"]
        read_only_fields = ["id", "created_at", "updated_at", "montant_tva", "montant_ttc"]


class SubventionExportSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubventionExport
        exclude = ["exploitation"]
        read_only_fields = ["id", "generated_at", "status", "file_url", "file_key"]
