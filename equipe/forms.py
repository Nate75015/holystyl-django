"""Formulaire d'ajout d'un membre d'équipe (salarié)."""

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Task, TeamMember


class TeamMemberForm(forms.ModelForm):
    """Crée un membre d'équipe : identité et rôle."""

    first_name = forms.CharField(
        label=_("Prénom"), max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "Jean"}),
    )
    last_name = forms.CharField(
        label=_("Nom"), max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "Dupont"}),
    )

    class Meta:
        model = TeamMember
        fields = ["email", "phone", "role"]
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
            # Édition : pré-remplir les champs non mappés depuis le nom complet.
            first, _sep, last = (member.name or "").partition(" ")
            self.fields["first_name"].initial = first
            self.fields["last_name"].initial = last

    def save(self, exploitation=None, managed_by=None, commit=True):
        member = super().save(commit=False)
        member.name = f"{self.cleaned_data['first_name']} {self.cleaned_data['last_name']}".strip()
        if exploitation is not None:
            member.exploitation = exploitation
        if managed_by is not None:
            member.managed_by = managed_by
        if commit:
            member.save()
        return member


class TaskForm(forms.ModelForm):
    """Crée une tâche (titre, assignation, priorité, échéance)."""

    class Meta:
        model = Task
        fields = ["title", "assigned_to", "priority", "status", "due_date", "description"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": _("Ex. Tailler la parcelle nord")}),
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": _("Détails (optionnel)")}),
            "due_date": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }
        labels = {
            "title": _("Titre"),
            "assigned_to": _("Assignée à"),
            "priority": _("Priorité"),
            "status": _("Statut"),
            "due_date": _("Échéance"),
            "description": _("Description"),
        }

    def __init__(self, *args, exploitation=None, **kwargs):
        super().__init__(*args, **kwargs)
        members = (
            TeamMember.objects.filter(exploitation=exploitation)
            if exploitation else TeamMember.objects.none()
        )
        self.fields["assigned_to"].queryset = members
        self.fields["assigned_to"].required = False
        self.fields["assigned_to"].empty_label = _("Non assignée")
        self.fields["description"].required = False
        self.fields["due_date"].required = False
        self.fields["due_date"].input_formats = ["%Y-%m-%dT%H:%M"]
