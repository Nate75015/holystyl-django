from django import forms

from .models import Parcelle


class ParcelleForm(forms.ModelForm):
    """Formulaire de création/édition de parcelle (wizard multi-étapes côté UI)."""

    class Meta:
        model = Parcelle
        fields = [
            # Étape 1 — identité & géométrie
            "name", "area", "latitude", "longitude", "boundaries",
            # Étape 2 — culture
            "culture", "variety", "kc_value", "tree_age_years",
            "planting_date", "plant_density_per_ha",
            # Étape 3 — sol
            "soil_type", "root_depth_cm", "soil_retention_mm_m", "soil_ph",
            # Étape 4 — irrigation
            "irrigation_type", "theoretical_flow_m3h", "nozzle_count",
            "nozzle_flow_lh", "row_spacing_m", "emitter_spacing_m", "service_pressure_bar",
            # Étape 5 — administratif
            "cadastral_ref", "commune", "official_area_ha", "status",
        ]
        widgets = {
            "boundaries": forms.HiddenInput(),
            "planting_date": forms.DateInput(attrs={"type": "date"}),
        }
