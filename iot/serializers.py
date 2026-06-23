from rest_framework import serializers

from .models import IotAlert, IotCommand, IotDevice, IotTelemetry, Threshold


class IotDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = IotDevice
        exclude = ["exploitation", "device_token"]
        read_only_fields = ["id", "status", "last_seen", "created_at", "updated_at"]


class IotTelemetrySerializer(serializers.ModelSerializer):
    class Meta:
        model = IotTelemetry
        fields = "__all__"


class IotCommandSerializer(serializers.ModelSerializer):
    class Meta:
        model = IotCommand
        fields = ["id", "device", "command_type", "parameters", "status", "created_at", "completed_at"]
        read_only_fields = ["id", "status", "created_at", "completed_at"]


class IotAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = IotAlert
        exclude = ["exploitation"]
        read_only_fields = ["id", "created_at"]


class ThresholdSerializer(serializers.ModelSerializer):
    class Meta:
        model = Threshold
        exclude = ["exploitation"]
        read_only_fields = ["id", "created_at", "updated_at"]
