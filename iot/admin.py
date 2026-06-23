from django.contrib import admin

from .models import IotAlert, IotCommand, IotDevice, IotTelemetry, Threshold


@admin.register(IotDevice)
class IotDeviceAdmin(admin.ModelAdmin):
    list_display = ("name", "device_id", "device_type", "brand", "status", "exploitation", "last_seen")
    list_filter = ("device_type", "brand", "status")
    search_fields = ("name", "device_id", "serial_number")


@admin.register(IotTelemetry)
class IotTelemetryAdmin(admin.ModelAdmin):
    list_display = ("device", "timestamp", "flow_rate_m3h", "pressure_bar", "power_kw", "soil_moisture")
    list_filter = ("device",)


@admin.register(IotCommand)
class IotCommandAdmin(admin.ModelAdmin):
    list_display = ("device", "command_type", "status", "created_at", "completed_at")
    list_filter = ("status",)


@admin.register(IotAlert)
class IotAlertAdmin(admin.ModelAdmin):
    list_display = ("title", "alert_type", "severity", "device", "acknowledged", "created_at")
    list_filter = ("alert_type", "severity", "acknowledged")


@admin.register(Threshold)
class ThresholdAdmin(admin.ModelAdmin):
    list_display = ("threshold_type", "exploitation", "min_value", "max_value", "active")
    list_filter = ("threshold_type", "active")
