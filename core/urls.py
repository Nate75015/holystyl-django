"""Routes du socle."""

from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("pulse/", views.dashboard, name="dashboard"),
    path("accueil/", views.dashboard, name="dashboard_accueil"),
    path("adresses/suggestions/", views.adresse_suggestions, name="adresse_suggestions"),
    path("adresses/details/", views.adresse_details, name="adresse_details"),
    path("healthz/", views.healthz, name="healthz"),
]
