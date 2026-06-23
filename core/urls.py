"""Routes du socle."""

from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("pulse/", views.dashboard, name="dashboard"),
    path("accueil/", views.dashboard, name="dashboard_accueil"),
    path("healthz/", views.healthz, name="healthz"),
]
