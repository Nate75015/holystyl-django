from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Parcelle, ParcelleCampagne


def _type_agriculture_optionnel(form):
    """Type d'agriculture : option vide = « hérité de l'exploitation »."""
    form.fields["type_agriculture"].required = False
    form.fields["type_agriculture"].widget.choices = (
        [("", _("Hérité de l'exploitation"))] + list(Parcelle.type_agriculture.field.choices)
    )


class ParcelleTypeAgricultureForm(forms.ModelForm):
    """Type d'agriculture seul — même champ que la fiche parcelle, éditable
    depuis l'écran campagne pour que les deux pages restent d'accord."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _type_agriculture_optionnel(self)

    class Meta:
        model = Parcelle
        fields = ["type_agriculture"]


class ParcelleForm(forms.ModelForm):
    """Formulaire de la parcelle (permanent : identité, géométrie, sol, cadastre)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _type_agriculture_optionnel(self)

    class Meta:
        model = Parcelle
        fields = [
            # Identité & géométrie
            "name", "area", "surface_utile", "type_agriculture",
            "latitude", "longitude", "boundaries",
            # Sol
            "soil_type", "root_depth_cm", "soil_retention_mm_m", "soil_ph",
            # Administratif
            "cadastral_ref", "commune", "official_area_ha", "status",
        ]
        widgets = {
            "boundaries": forms.HiddenInput(),
        }


class ParcelleCampagneForm(forms.ModelForm):
    """Culture et irrigation d'une parcelle pour une campagne donnée."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Libellé optionnel : repli sur la campagne courante si laissé vide.
        self.fields["libelle"].required = False
        if not self.instance.pk and not self.initial.get("libelle"):
            self.fields["libelle"].initial = ParcelleCampagne.libelle_courant()

        # « Culture » = liste déroulante alimentée par la base de cultures (/cultures/).
        from agronomie.models import CultureKc

        noms = list(CultureKc.objects.values_list("nom", flat=True).distinct())
        current = (getattr(self.instance, "culture", "") or "").strip()
        if current and current not in noms:  # ne pas perdre une valeur historique hors base
            noms.insert(0, current)
        choices = [("", _("— Choisir une culture —"))] + [(n, n) for n in noms]
        self.fields["culture"].widget = forms.Select(choices=choices)
        self.fields["culture"].required = False

        # « Type de culture » = catégorie du référentiel (céréales, vigne, fruits…).
        self.fields["type_culture"].widget = forms.Select(
            choices=[("", _("— Déduit de la culture —"))] + list(ParcelleCampagne.types_culture())
        )
        self.fields["type_culture"].required = False

    def clean_type_culture(self):
        """Type laissé vide → repli sur la catégorie du référentiel de cultures."""
        type_culture = (self.cleaned_data.get("type_culture") or "").strip()
        if type_culture:
            return type_culture
        return ParcelleCampagne.type_culture_de(self.data.get("culture"))

    def clean_libelle(self):
        # `parcelle` n'étant pas un champ du formulaire, la contrainte d'unicité
        # (parcelle, libelle) n'est pas vérifiée automatiquement : on la valide ici.
        libelle = (self.cleaned_data.get("libelle") or "").strip()
        if not libelle:
            libelle = ParcelleCampagne.libelle_courant()
        parcelle_id = getattr(self.instance, "parcelle_id", None)
        if parcelle_id:
            qs = ParcelleCampagne.objects.filter(parcelle_id=parcelle_id, libelle=libelle)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(_("Cette campagne existe déjà pour cette parcelle."))
        return libelle

    class Meta:
        model = ParcelleCampagne
        fields = [
            "libelle",
            # Culture
            "type_culture", "culture", "variety", "kc_value", "tree_age_years",
            "planting_date", "plant_density_per_ha",
            # Irrigation
            "irrigation_type", "theoretical_flow_m3h", "nozzle_count",
            "nozzle_flow_lh", "row_spacing_m", "emitter_spacing_m", "service_pressure_bar",
        ]
        widgets = {
            "planting_date": forms.DateInput(attrs={"type": "date"}),
        }
