from rest_framework import serializers

from .models import (
    EquipmentCatalog,
    InterventionReport,
    PlanningAbsence,
    PlanningTask,
    PlanningTimeLog,
)


class _TenantSerializer(serializers.ModelSerializer):
    class Meta:
        exclude = ["exploitation"]
        read_only_fields = ["id", "created_at", "updated_at"]


class PlanningTaskSerializer(_TenantSerializer):
    class Meta(_TenantSerializer.Meta):
        model = PlanningTask


class PlanningAbsenceSerializer(_TenantSerializer):
    class Meta(_TenantSerializer.Meta):
        model = PlanningAbsence


class EquipmentCatalogSerializer(_TenantSerializer):
    class Meta(_TenantSerializer.Meta):
        model = EquipmentCatalog


class PlanningTimeLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanningTimeLog
        exclude = ["exploitation"]
        read_only_fields = ["id", "created_at"]


class InterventionReportSerializer(_TenantSerializer):
    class Meta(_TenantSerializer.Meta):
        model = InterventionReport
