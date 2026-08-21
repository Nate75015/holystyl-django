"""Routes du socle.

`core:dashboard` et `core:dashboard_accueil` sont conservés en alias vers
l'aiguillage de l'app `dashboard` : ils sont référencés dans huit templates et
dans la nav (`core.context_processors`), on ne casse pas ces liens.
"""

from django.urls import path

from dashboard import views as dashboard_views

from . import views

app_name = "core"

urlpatterns = [
    path("pulse/", dashboard_views.index, name="dashboard"),
    path("accueil/", dashboard_views.index, name="dashboard_accueil"),
    path("adresses/suggestions/", views.adresse_suggestions, name="adresse_suggestions"),
    path("adresses/details/", views.adresse_details, name="adresse_details"),
    path("healthz/", views.healthz, name="healthz"),
]
