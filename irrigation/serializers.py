from rest_framework import serializers

from .models import (
    BassinageEvent,
    DtiScore,
    IrrigationProgram,
    IrrigationSession,
    IrrigationZone,
    PumpingStation,
    WaterMeter,
    WaterQuota,
)


class _TenantSerializer(serializers.ModelSerializer):
    """Base : exclut exploitation (injectée par la vue)."""

    class Meta:
        exclude = ["exploitation"]
        read_only_fields = ["id"]


class IrrigationZoneSerializer(_TenantSerializer):
    class Meta(_TenantSerializer.Meta):
        model = IrrigationZone


class IrrigationProgramSerializer(_TenantSerializer):
    class Meta(_TenantSerializer.Meta):
        model = IrrigationProgram


class IrrigationSessionSerializer(_TenantSerializer):
    class Meta(_TenantSerializer.Meta):
        model = IrrigationSession


class PumpingStationSerializer(_TenantSerializer):
    class Meta(_TenantSerializer.Meta):
        model = PumpingStation


class BassinageEventSerializer(_TenantSerializer):
    class Meta(_TenantSerializer.Meta):
        model = BassinageEvent


class WaterMeterSerializer(_TenantSerializer):
    class Meta(_TenantSerializer.Meta):
        model = WaterMeter


class WaterQuotaSerializer(_TenantSerializer):
    class Meta(_TenantSerializer.Meta):
        model = WaterQuota


class DtiScoreSerializer(_TenantSerializer):
    class Meta(_TenantSerializer.Meta):
        model = DtiScore
