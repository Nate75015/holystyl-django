from rest_framework import serializers

from .models import CropStage, Parcelle, ParcelleCampagne


class CropStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CropStage
        fields = [
            "id", "parcelle_campagne", "stage_name", "stage_code",
            "start_date", "end_date", "kc_value", "root_depth_m", "notes",
        ]


class ParcelleCampagneSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParcelleCampagne
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


class ParcelleSerializer(serializers.ModelSerializer):
    # Culture / irrigation : portées par la campagne courante, exposées en
    # lecture seule sur la parcelle (les écritures passent par /parcelle-campagnes/).
    culture = serializers.ReadOnlyField()
    variety = serializers.ReadOnlyField()
    kc_value = serializers.ReadOnlyField()
    tree_age_years = serializers.ReadOnlyField()
    planting_date = serializers.ReadOnlyField()
    plant_density_per_ha = serializers.ReadOnlyField()
    irrigation_type = serializers.ReadOnlyField()
    theoretical_flow_m3h = serializers.ReadOnlyField()
    nozzle_count = serializers.ReadOnlyField()
    nozzle_flow_lh = serializers.ReadOnlyField()
    row_spacing_m = serializers.ReadOnlyField()
    emitter_spacing_m = serializers.ReadOnlyField()
    service_pressure_bar = serializers.ReadOnlyField()

    class Meta:
        model = Parcelle
        exclude = ["exploitation"]
        read_only_fields = ["id", "created_at", "updated_at"]
