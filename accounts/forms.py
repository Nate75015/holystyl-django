"""Formulaires d'inscription / connexion (email + mot de passe)."""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class EmailAuthenticationForm(AuthenticationForm):
    """Connexion par email (le champ 'username' devient l'email)."""

    username = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}),
    )


class RegisterForm(UserCreationForm):
    """Inscription : identité, date de naissance, adresse, email et mot de passe."""

    first_name = forms.CharField(label=_("Prénom"), max_length=150)
    last_name = forms.CharField(label=_("Nom"), max_length=150)
    birth_date = forms.DateField(
        label=_("Date de naissance"),
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "birth_date",
            "address_number",
            "address_street",
            "address_zip",
            "address_city",
        )

    field_order = [
        "first_name",
        "last_name",
        "email",
        "birth_date",
        "address_number",
        "address_street",
        "address_zip",
        "address_city",
        "password1",
        "password2",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # L'adresse complète est demandée à l'inscription.
        for name in ("address_number", "address_street", "address_zip", "address_city"):
            self.fields[name].required = True

    def save(self, commit=True):
        user = super().save(commit=False)
        # full_name est dérivé du prénom + nom dans User.save().
        if commit:
            user.save()
        return user
