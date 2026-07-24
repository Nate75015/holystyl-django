from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Parcelle


class ParcelleForm(forms.ModelForm):
    """Formulaire de création/édition de parcelle (wizard multi-étapes côté UI)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # « Culture » = liste déroulante alimentée par la base de cultures (/cultures/).
        from agronomie.models import CultureKc

        noms = list(CultureKc.objects.values_list("nom", flat=True).distinct())
        current = (getattr(self.instance, "culture", "") or "").strip()
        if current and current not in noms:  # ne pas perdre une valeur historique hors base
            noms.insert(0, current)
        choices = [("", _("— Choisir une culture —"))] + [(n, n) for n in noms]
        self.fields["culture"].widget = forms.Select(choices=choices)
        self.fields["culture"].required = False

        # Type d'agriculture : option vide = « hérité de l'exploitation ».
        self.fields["type_agriculture"].required = False
        self.fields["type_agriculture"].widget.choices = (
            [("", _("Hérité de l'exploitation"))] + list(Parcelle.type_agriculture.field.choices)
        )

    class Meta:
        model = Parcelle
        fields = [
            # Étape 1 — identité & géométrie
            "name", "area", "surface_utile", "latitude", "longitude", "boundaries",
            # Étape 2 — culture
            "type_agriculture",
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
