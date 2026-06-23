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
    """Inscription : email, nom complet, mot de passe."""

    full_name = forms.CharField(label=_("Nom complet"), max_length=255, required=False)

    class Meta:
        model = User
        fields = ("email", "full_name")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.full_name = self.cleaned_data.get("full_name", "")
        if commit:
            user.save()
        return user
