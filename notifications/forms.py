"""Formulaire de création d'une règle d'alerte."""

from django import forms
from django.utils.translation import gettext_lazy as _

from meteo.models import VilleMeteo

from .models import NotificationRule

#: Seuls ces types/conditions sont évalués par `notifications.tasks.evaluate_rules`.
#: Le modèle en connaît d'autres (irrigation, capteur, changement d'état…) mais aucune
#: source de données ne les alimente : les proposer créerait des règles muettes.
SUPPORTED_TYPES = [NotificationRule.Type.METEO]
SUPPORTED_CONDITIONS = list(NotificationRule.THRESHOLD_CONDITIONS)


class NotificationRuleForm(forms.ModelForm):
    """Crée une règle : nom, type surveillé, lieu, grandeur, condition et seuil.

    Les colonnes `type`/`condition_type` sont libres côté modèle : le formulaire web
    les restreint aux valeurs réellement évaluables.
    """

    # `x-model` pilote l'affichage des champs dépendants du type côté template.
    type = forms.ChoiceField(
        label=_("Type"),
        choices=[(t.value, t.label) for t in SUPPORTED_TYPES],
        initial=NotificationRule.Type.METEO,
        widget=forms.Select(attrs={"x-model": "ruleType"}),
    )
    condition_type = forms.ChoiceField(
        label=_("Condition"),
        choices=[(c.value, c.label) for c in SUPPORTED_CONDITIONS],
        initial=NotificationRule.ConditionType.SEUIL_DEPASSE,
    )

    class Meta:
        model = NotificationRule
        fields = ["name", "type", "ville", "metric", "condition_type", "threshold"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": _("Ex. Canicule sur la parcelle nord")}),
            "threshold": forms.NumberInput(attrs={"step": "0.01", "placeholder": "30"}),
        }
        labels = {
            "name": _("Nom de la règle"),
            "threshold": _("Seuil"),
        }

    def __init__(self, *args, exploitation=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["threshold"].required = False
        # Lieu et grandeur n'ont de sens que pour une règle météo : exigés dans clean().
        self.fields["ville"].required = False
        self.fields["metric"].required = False
        self.fields["ville"].queryset = (
            VilleMeteo.objects.filter(exploitation=exploitation)
            if exploitation else VilleMeteo.objects.none()
        )
        self.fields["ville"].empty_label = _("Choisir un lieu…")

    @property
    def has_villes(self):
        """Permet au template de guider vers /meteo/ quand aucun lieu n'est enregistré."""
        return self.fields["ville"].queryset.exists()

    def clean(self):
        cleaned = super().clean()
        rule_type, condition = cleaned.get("type"), cleaned.get("condition_type")

        if condition in NotificationRule.THRESHOLD_CONDITIONS and cleaned.get("threshold") is None:
            self.add_error("threshold", _("Un seuil est requis pour cette condition."))

        if rule_type == NotificationRule.Type.METEO:
            if not cleaned.get("ville"):
                self.add_error("ville", _("Choisissez le lieu à surveiller."))
            if not cleaned.get("metric"):
                self.add_error("metric", _("Choisissez la grandeur à surveiller."))
        else:
            # Changer de type ne doit pas laisser lieu ni grandeur résiduels.
            cleaned["ville"] = None
            cleaned["metric"] = ""

        return cleaned

    def save(self, commit=True):
        rule = super().save(commit=False)
        # Le seuil change → l'état mémorisé ne veut plus rien dire : on réarme la règle
        # pour que la prochaine évaluation notifie sur le nouveau franchissement.
        if {"threshold", "condition_type", "metric", "ville"} & set(self.changed_data):
            rule.is_breaching = False
        if commit:
            rule.save()
        return rule
