from rest_framework import serializers

from .models import CropStage, Parcelle


class CropStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CropStage
        fields = [
            "id", "parcelle", "stage_name", "stage_code",
            "start_date", "end_date", "kc_value", "root_depth_m", "notes",
        ]


class ParcelleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parcelle
        exclude = ["exploitation"]
        read_only_fields = ["id", "created_at", "updated_at"]
