"""Vues d'authentification : connexion, inscription, déconnexion."""

from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import EmailAuthenticationForm, RegisterForm


class HolystylLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True


class HolystylLogoutView(LogoutView):
    pass


class RegisterView(CreateView):
    template_name = "accounts/register.html"
    form_class = RegisterForm
    success_url = reverse_lazy("core:dashboard")

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response
