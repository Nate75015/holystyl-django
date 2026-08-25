"""Routes d'authentification."""

from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.HolystylLoginView.as_view(), name="login"),
    path("logout/", views.HolystylLogoutView.as_view(), name="logout"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("profil/", views.choix_profil, name="choix_profil"),
]
