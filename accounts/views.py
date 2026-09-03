"""Vues d'authentification : connexion, inscription, déconnexion."""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.views.generic import CreateView

from core import espaces as espaces_service

from .forms import EmailAuthenticationForm, RegisterForm


class IsidorLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True


class IsidorLogoutView(LogoutView):
    pass


#: Ce que chaque profil recouvre, en une phrase, pour éclairer le choix.
DESCRIPTIONS_PROFIL = {
    espaces_service.EXPLOITANT: _("Je dirige une exploitation et je la gère sur Isidor."),
    espaces_service.EMPLOYE: _("Je travaille pour une exploitation qui utilise Isidor."),
    espaces_service.BAILLEUR: _("Je loue des terres à une exploitation."),
    espaces_service.COMPTABLE: _("Je tiens la comptabilité d'une exploitation."),
}


@login_required
def choix_profil(request):
    """Qui êtes-vous ? — première connexion, sans invitation.

    Un compte créé sur invitation arrive déjà rattaché : son espace existe et
    cette page ne le concerne pas. Sans rattachement, on demande le profil
    plutôt que de supposer un chef d'entreprise, ce que faisait l'accueil
    jusqu'ici.

    Le choix n'ouvre aucun droit : seul un rattachement le fait. L'exploitant
    crée son exploitation dans la foulée ; les autres attendent d'être
    rattachés par l'exploitation qui les emploie, les loge ou les mandate.
    """
    if espaces_service.espaces_de(request.user):
        return redirect("core:dashboard")

    if request.method == "POST":
        choix = request.POST.get("profil")
        if choix not in espaces_service.PROFILS_DECLARABLES:
            messages.error(request, _("Choisissez un profil pour continuer."))
            return redirect("accounts:choix_profil")
        request.user.profil_souhaite = choix
        request.user.save(update_fields=["profil_souhaite"])
        # Chacun arrive sur son tableau de bord. Sans rattachement il est vide,
        # mais il porte l'invite qui convient : créer son exploitation pour un
        # chef d'entreprise, se faire rattacher pour les autres.
        return redirect(espaces_service.tableau_de_bord(choix))

    profils = [
        {**profil, "description": DESCRIPTIONS_PROFIL.get(profil["cle"], "")}
        for profil in espaces_service.profils_declarables()
    ]
    return render(request, "accounts/choix_profil.html", {
        "profils": profils,
        "layout_nu": True,
        "page_title": _("Votre profil"),
    })


class RegisterView(CreateView):
    template_name = "accounts/register.html"
    form_class = RegisterForm
    success_url = reverse_lazy("core:dashboard")

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response
