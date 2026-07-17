"""Formulaire d'édition d'une analyse de sol (tous les champs du rapport labo)."""

from django import forms

from .models import AnalyseSol

# Champs présentés à l'édition, groupés par section (mêmes regroupements que l'admin).
# La parcelle et la date restent modifiables ; exploitation/document/created_at non.
FIELD_GROUPS = (
    ("Général", ("parcelle", "date")),
    ("Identification (labo)", (
        "laboratoire", "numero_laboratoire", "reference", "technicien", "commune",
        "profondeur_prelevement", "date_prelevement", "date_arrivee_labo", "date_expedition",
    )),
    ("pH & calcaire", ("ph", "ph_kcl", "ec", "calcaire_total", "calcaire_actif", "calcium_cao")),
    ("MO, carbone & azote", (
        "matiere_organique", "carbone_organique", "azote_total", "c_n",
        "coefficient_k2", "azote_ammoniacal",
    )),
    ("Éléments majeurs", (
        "phosphore_assimilable", "phosphore_olsen", "potassium_echangeable",
        "magnesium_mgo", "sodium_na2o",
    )),
    ("Oligo-éléments", ("bore", "cuivre", "fer", "manganese", "zinc")),
    ("CEC & équilibre cationique", (
        "cec", "taux_saturation", "ca_cec", "k_cec", "mg_cec", "na_cec", "h_cec",
    )),
    ("Granulométrie / texture", (
        "type_sol", "argile", "limons_fins", "limons_grossiers",
        "sables_fins", "sables_grossiers",
    )),
    ("Propriétés physiques & réserve en eau", (
        "humidite", "matiere_seche", "refus_2mm", "densite_apparente",
        "reserve_utile", "reserve_facilement_utilisable", "capacite_retention_pf25",
        "capacite_retention_pf42", "indice_battance", "risque_battance",
    )),
    ("Éléments traces métalliques", (
        "cadmium", "chrome", "cuivre_total", "mercure", "nickel", "plomb", "zinc_total",
        "arsenic", "cobalt", "molybdene", "selenium", "fer_total", "manganese_total",
        "bore_total", "aluminium_echangeable", "aluminium_total",
    )),
    ("Contaminants organiques (annexe)", ("somme_16_hap", "somme_7_pcb")),
    ("Notes", ("notes",)),
)

_INPUT_CLASS = (
    "w-full rounded-lg border border-slate-200 bg-transparent px-3 py-2 text-sm "
    "focus:border-brand focus:outline-none dark:border-white/10 dark:[color-scheme:dark]"
)


class AnalyseSolForm(forms.ModelForm):
    class Meta:
        model = AnalyseSol
        fields = [name for _title, names in FIELD_GROUPS for name in names]
        widgets = {
            "date": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "date_prelevement": forms.DateInput(attrs={"type": "date"}),
            "date_arrivee_labo": forms.DateInput(attrs={"type": "date"}),
            "date_expedition": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        exploitation = kwargs.pop("exploitation", None)
        super().__init__(*args, **kwargs)
        # La liste des parcelles est limitée à l'exploitation de l'utilisateur.
        if exploitation is not None:
            self.fields["parcelle"].queryset = self.fields["parcelle"].queryset.filter(
                exploitation=exploitation
            )
        # Les <input type="date/datetime-local"> exigent la valeur au format ISO.
        for name in ("date_prelevement", "date_arrivee_labo", "date_expedition"):
            self.fields[name].input_formats = ["%Y-%m-%d"]
        self.fields["date"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"]
        # Applique le style commun à tous les widgets.
        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (css + " " + _INPUT_CLASS).strip()
