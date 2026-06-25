"""Formulaire d'ajout d'un membre d'équipe (salarié)."""

from django import forms
from django.contrib.auth.hashers import make_password
from django.utils.translation import gettext_lazy as _

from .models import TeamMember

# Langues proposées au salarié (valeur stockée dans preferred_locale).
LOCALE_CHOICES = [
    ("fr", "🇫🇷 Français"),
    ("en", "🇬🇧 English"),
    ("es", "🇪🇸 Español"),
    ("pt", "🇵🇹 Português"),
    ("pl", "🇵🇱 Polski"),
]

# Modules de l'application auxquels le salarié peut accéder.
MODULE_CHOICES = [
    ("planning", _("Planning")),
    ("parcelles", _("Parcelles")),
    ("irrigation", _("Irrigation")),
    ("iot", _("Capteurs & IoT")),
    ("ia", _("Assistant IA")),
    ("taches", _("Tâches")),
    ("cultures", _("Cultures")),
    ("charges", _("Charges")),
    ("biodiversite", _("Biodiversité")),
]

# Modules cochés par défaut à la création.
DEFAULT_MODULES = ["planning", "parcelles", "irrigation", "iot", "ia", "taches"]


class TeamMemberForm(forms.ModelForm):
    """Crée un membre d'équipe : identité, accès (mot de passe), langue, modules."""

    first_name = forms.CharField(
        label=_("Prénom"), max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "Jean"}),
    )
    last_name = forms.CharField(
        label=_("Nom"), max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "Dupont"}),
    )
    password = forms.CharField(
        label=_("Mot de passe"),
        min_length=4,
        widget=forms.PasswordInput(attrs={"placeholder": "••••••••", "autocomplete": "new-password"}),
        help_text=_("Min. 4 caractères — le salarié utilisera son email + ce mot de passe pour se connecter."),
    )
    preferred_locale = forms.ChoiceField(label=_("Langue"), choices=LOCALE_CHOICES, initial="fr")
    modules = forms.MultipleChoiceField(
        label=_("Modules autorisés"),
        choices=MODULE_CHOICES,
        initial=DEFAULT_MODULES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "h-4 w-4 shrink-0 accent-[#28738f]"}),
    )

    class Meta:
        model = TeamMember
        fields = ["email", "phone", "role", "preferred_locale"]
        widgets = {
            "email": forms.EmailInput(attrs={"placeholder": "jean@exemple.fr"}),
            "phone": forms.TextInput(attrs={"placeholder": "+33 6 12 34 56 78"}),
        }
        labels = {
            "email": _("Email"),
            "phone": _("Téléphone"),
            "role": _("Rôle"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # L'email sert d'identifiant de connexion : obligatoire.
        self.fields["email"].required = True

        member = self.instance
        if member and member.pk:
            # Édition : pré-remplir les champs non mappés et rendre le mot de
            # passe optionnel (vide = on garde l'actuel).
            first, _sep, last = (member.name or "").partition(" ")
            self.fields["first_name"].initial = first
            self.fields["last_name"].initial = last
            self.fields["modules"].initial = member.allowed_modules or []
            self.fields["password"].required = False
            self.fields["password"].help_text = _("Laissez vide pour conserver le mot de passe actuel.")

    def save(self, exploitation=None, managed_by=None, commit=True):
        member = super().save(commit=False)
        member.name = f"{self.cleaned_data['first_name']} {self.cleaned_data['last_name']}".strip()
        password = self.cleaned_data.get("password")
        if password:
            member.password_hash = make_password(password)
        member.allowed_modules = self.cleaned_data.get("modules", [])
        if exploitation is not None:
            member.exploitation = exploitation
        if managed_by is not None:
            member.managed_by = managed_by
        if commit:
            member.save()
        return member
